# Changelog

## 0.2.2 — 2026-11-09

First public source and GitHub release, based on the locally validated 0.2.0 bridge.

- Publish the standalone Windows MCP server and Codex plugin under MIT.
- Add English/Chinese overview, installation and configuration, minimal examples, tool inventory, validation boundaries and related-work research.
- Add an explicit release file list, reproducible ZIP builder, per-file hashes and archive checksum.
- Include 68 self-contained offline tests; omit seven private native-fixture tests and their data.
- Resolve temporary fixture paths before assertions so Windows short-path aliases on GitHub runners are compared correctly. Runtime path resolution is unchanged.
- Keep the content of all 29 runtime files from the validated 0.2.0 baseline; normalize text line endings to LF for portable source archives. No new circuit features or vendor-model changes.

Validated simulator: Simplified Chinese TINA-TI 9.3.150.328SF-TI on Windows. Other versions/languages and a second computer remain unverified. Fourier is native-plot only; noise support is output spectral density only.

## 0.2.1 — 2026-11-09 (publication candidate)

Initial source tag, superseded before Release publication by 0.2.2 after hosted Windows testing found a short-path assumption in two test assertions. The tag is retained for history; no final 0.2.1 Release is published.
