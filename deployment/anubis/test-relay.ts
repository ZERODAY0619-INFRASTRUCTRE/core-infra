import { strict as assert } from "node:assert";
import { createHash, randomBytes } from "node:crypto";
import { buildAnubisGate } from "/source/caddy-anubis.ts";

const host = "sso.example.test";
const userAgent = "Safari-relay-regression";
const dashboardHost = "dashboard.example.test";
const gate = buildAnubisGate("example.test", { roamingHost: host, roamingHosts: [dashboardHost], apiHosts: [dashboardHost] })!;
const arrayPaths = ["/api/user/orgs", "/api/user/teams", "/api/alertmanager/grafana/api/v2/alerts"];
const backend = Bun.serve({
    hostname: "127.0.0.1", port: 9000,
    async fetch(request, server) {
        if (request.headers.get("Upgrade") === "websocket" && server.upgrade(request)) return;
        if (arrayPaths.includes(new URL(request.url).pathname)) {
            if (!request.headers.get("Cookie")?.includes("grafana_test_session=present")) {
                return Response.json({ message: "Unauthorized" }, { status: 401 });
            }
            return Response.json([]);
        }
        return Response.json({ method: request.method, body: await request.text() });
    },
    websocket: { message(socket, message) { socket.send(message); } },
});
await Bun.write("/tmp/policy.json", JSON.stringify({ bots: [{
    name: "browser", path_regex: ".*", action: "CHALLENGE", challenge: { algorithm: "fast", difficulty: 2 },
}] }));
await Bun.write("/tmp/caddy.json", JSON.stringify({
    admin: { disabled: true },
    logging: { logs: { default: { level: "ERROR" } } },
    apps: { http: { servers: {
        gate: {
            listen: ["127.0.0.1:9080"],
            trusted_proxies: { source: "static", ranges: ["127.0.0.1/32"] },
            client_ip_headers: ["X-Forwarded-For"],
            routes: [...gate.routes.slice(1), { handle: [{ handler: "reverse_proxy", upstreams: [{ dial: "127.0.0.1:9000" }] }] }],
        },
        success: gate.successServer,
    } } },
}));
const processes = [
    Bun.spawn(["/caddy", "run", "--config", "/tmp/caddy.json"], { stdout: "ignore", stderr: "inherit",
        env: { ...process.env, XDG_DATA_HOME: "/tmp/data", XDG_CONFIG_HOME: "/tmp/config" } }),
    Bun.spawn(["/ko-app/anubis"], { stdout: "ignore", stderr: "ignore", env: {
        ...process.env,
        BIND: "127.0.0.1:8923", METRICS_BIND: "127.0.0.1:8925", TARGET: "http://127.0.0.1:8924",
        POLICY_FNAME: "/tmp/policy.json", JWT_RESTRICTION_HEADER: "X-Cpm-Anubis-Binding",
        COOKIE_SECURE: "false", COOKIE_PARTITIONED: "false", REDIRECT_DOMAINS: "*.example.test",
        ED25519_PRIVATE_KEY_HEX: randomBytes(32).toString("hex"),
    } }),
];

async function request(path: string, address: string, cookie = "", requestHost = host, agent = userAgent, method = "GET", body?: string) {
    return fetch("http://127.0.0.1:9080" + path, {
        method, body, redirect: "manual", headers: {
            Host: requestHost, "User-Agent": agent, Cookie: cookie, "X-Forwarded-For": address,
            "X-Cpm-Anubis-Binding": "client-supplied-value-must-be-overwritten",
        },
    });
}

async function solve(requestHost = host) {
    const response = await request("/login", "198.51.100.11", "", requestHost);
    const verificationCookie = response.headers.getSetCookie().filter(value => !value.includes("-auth-")).map(value => value.split(";")[0]).join("; ");
    const html = await response.text();
    const match = html.match(/<script[^>]*id=["']?anubis_challenge["']?[^>]*>(.*?)<\/script>/s);
    assert.ok(match, "An unsigned request must receive a challenge");
    const { challenge, rules } = JSON.parse(match[1]);
    let nonce = 0;
    let digest: string;
    do { digest = createHash("sha256").update(challenge.randomData + nonce).digest("hex"); nonce++; }
    while (!digest.startsWith("0".repeat(rules.difficulty)));
    const query = new URLSearchParams({ id: challenge.id, response: digest, nonce: String(nonce - 1),
        redir: "http://" + requestHost + "/login", elapsedTime: "1000" });
    const verified = await request("/.within.website/x/cmd/anubis/api/pass-challenge?" + query, "198.51.100.11", verificationCookie, requestHost);
    assert.equal(verified.status, 302);
    const cookie = verified.headers.getSetCookie().find(value => value.includes("-auth-") && !value.includes("Max-Age=0"));
    assert.ok(cookie, "A valid proof must issue a signed cookie");
    return cookie.split(";")[0];
}

try {
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
        try { ready = (await fetch("http://127.0.0.1:8925/healthz")).ok && (await request("/login", "198.51.100.11")).ok; }
        catch {}
        if (ready) break;
        await Bun.sleep(100);
    }
    assert.ok(ready, "Isolated services must become ready");
    const cookie = await solve();
    for (const address of ["198.51.100.11", "198.51.100.12", "2001:db8::12"]) {
        const response = await request("/api/login", address, cookie, host, userAgent, "POST", "test-body");
        assert.deepEqual(await response.json(), { method: "POST", body: "test-body" });
        assert.equal(response.headers.getSetCookie().length, 0);
    }
    console.log("PASS: SSO signed cookie survives IPv4/IPv6 changes and preserves POST bodies");
    await new Promise<void>((resolve, reject) => {
        const socket = new WebSocket("ws://127.0.0.1:9080/ws/client/", { headers: {
            Host: host, "User-Agent": userAgent, Cookie: cookie, "X-Forwarded-For": "198.51.100.99",
        } });
        const timer = setTimeout(() => { socket.close(); reject(new Error("WebSocket timeout")); }, 5000);
        socket.onopen = () => socket.send("relay-test");
        socket.onmessage = event => { assert.equal(event.data, "relay-test"); clearTimeout(timer); socket.close(); resolve(); };
        socket.onerror = () => { clearTimeout(timer); reject(new Error("WebSocket failed")); };
    });
    console.log("PASS: WebSocket handshake and message survive a different client IP");
    for (const [credential, agent] of [["", userAgent], [cookie + "tampered", userAgent], [cookie, "different-browser"]]) {
        assert.match(await (await request("/api/login", "198.51.100.12", credential, host, agent)).text(), /Making sure/);
    }
    console.log("PASS: missing, tampered and different-browser cookies remain challenged");
    const dashboardCookie = await solve(dashboardHost);
    for (const path of arrayPaths) {
        const challenge = await request(path, "198.51.100.12", "", dashboardHost);
        assert.equal(challenge.status, 403);
        assert.equal(challenge.headers.get("Content-Type"), "application/problem+json");
        assert.equal((await challenge.json()).code, "proxy_verification_required");
        assert.equal(challenge.headers.getSetCookie().length, 0);
        assert.match(challenge.headers.get("Cache-Control")!, /no-store/);
        const originUnauthorized = await request(path, "198.51.100.12", dashboardCookie, dashboardHost);
        assert.equal(originUnauthorized.status, 401);
        assert.equal(originUnauthorized.headers.get("X-Anubis-Gate"), "passed");
        const authenticated = await request(path, "2001:db8::15", dashboardCookie + "; grafana_test_session=present", dashboardHost);
        assert.equal(authenticated.status, 200);
        assert.deepEqual(await authenticated.json(), []);
        assert.match(authenticated.headers.get("Cache-Control")!, /no-store/);
    }
    console.log("PASS: Grafana API challenge errors are noncacheable 403 problems without cookie deletion; origin authentication and JSON arrays survive roaming");
    assert.match(await (await request("/login", "198.51.100.12", "", dashboardHost)).text(), /Making sure/);
    console.log("PASS: Grafana page navigation retains interactive verification");
    const otherHost = "monitorss.example.test";
    const otherCookie = await solve(otherHost);
    assert.equal((await request("/api", "198.51.100.11", otherCookie, otherHost)).headers.get("X-Anubis-Gate"), "passed");
    assert.match(await (await request("/api", "198.51.100.12", otherCookie, otherHost)).text(), /Making sure/);
    console.log("PASS: other hosts retain IP binding despite a forged binding header");
} finally {
    for (const process of processes) process.kill("SIGTERM");
    await Promise.all(processes.map(process => process.exited));
    backend.stop();
}
