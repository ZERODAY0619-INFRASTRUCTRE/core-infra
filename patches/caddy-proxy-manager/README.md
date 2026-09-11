# Patch series convention

This project follows the Linux kernel's **patch-mail format and organization**,
not kernel C coding style for this TypeScript application.
Reference: https://cdn.kernel.org/doc/html/latest/process/submitting-patches.html

- Generate patches with `git format-patch --numbered --cover-letter --base=BASE`.
- Use `0001-subsystem-imperative-summary.patch`, numbered in dependency order.
- Each message has `From`, `Date`, and `Subject: [PATCH n/m] subsystem: summary`.
- Keep the subject within 75 characters, with no final full stop. Explain the
  problem and resulting behavior in the body, wrapping prose around 72 columns.
- Put one related functional change in each commit. Include its related tests.
- `0000-cover-letter.patch` explains the whole series; it is not applied.
- `series` lists the numbered patches; `upstream.json` pins hashes and the base.
- Keep binary font changes and license files intact. `git am --keep-cr` preserves
  the upstream license files' CRLF bytes.

Current series:

1. OAuth role synchronization
2. Access-list account boundary
3. Proxy authentication validation and transport helpers
4. L4 port override filtering
5. Tailnet-aware analytics
6. Shared branding primitives and bundled fonts
7. Status responses, maintenance and error feedback
8. Management screen presentation
9. Shared image builds and custom CI
10. Anubis global/per-host policy, validated runtime settings and rollback
11. Anubis console toggles and challenge settings
12. Non-root Anubis runtime supervisor with health acknowledgements

Author: zeroday0619 <escha@zeroday0619.dev>

`Signed-off-by` is a personal Developer Certificate of Origin attestation.
The conversion does not fabricate DCO, Reviewed-by or Tested-by trailers.
The current series has no Signed-off-by trailers and is therefore not claimed
ready for submission to the Linux kernel. After personally verifying the DCO,
authors can use `git commit -s` (or amend their own commits) and export again.
`app-source.py export --require-signoff` rejects any missing sign-off trailer.
The presence of a trailer is a format check, not proof of the attestation.

For a revised public submission use `[PATCH v2 n/m]` and describe changes from
v1 below the `---` separator or in the cover letter; do not put revision-only
notes in the permanent commit message. This local initial series is v1.
