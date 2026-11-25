FROM grafana/grafana:13.3.2@sha256:81556409ba48b2b922e0adb69a2511337d8ba7578f11962eefa6149a2d815101 AS upstream
FROM python:3.12-alpine AS patch
COPY --from=upstream /usr/share/grafana/public/build/56591.a0aa7fa32cd1074d.js /patched/56591.a0aa7fa32cd1074d.js
COPY --from=upstream /usr/share/grafana/public/build/runtime.f6bd22711abefe1a.js /patched/runtime.f6bd22711abefe1a.js
COPY --from=upstream /usr/share/grafana/public/build/assets-manifest.json /patched/assets-manifest.json
COPY --from=upstream /usr/share/grafana/public/build/18631.ceb2a2734f477243.js /patched/18631.ceb2a2734f477243.js
COPY patches/ /patches/
RUN python /patches/package-home.py /patched
FROM upstream
COPY --from=patch /patched/ /usr/share/grafana/public/build/
