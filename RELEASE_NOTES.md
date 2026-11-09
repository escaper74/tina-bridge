# TINA Bridge 0.2.2

First public release of the native Windows TINA-TI MCP adapter.

## Included

- 32 MCP tools and 15 native component templates.
- Native schematic reading/query/comparison and editing into new `.TSC` files.
- Native device/library selection, source waveforms, seven analysis entry points, numerical measurements and persistent parameter batches.
- Codex repository marketplace, operating skill, direct stdio MCP configuration and independent Python setup.
- English/Chinese documentation, related-work research, MIT license, third-party notices, offline tests and reproducible ZIP build.

The runtime content is inherited from the validated 0.2.0 package with LF text normalization. This release adds public packaging and documentation, not additional simulator functionality.

## Compatibility and limits

Validated with **Windows, Simplified Chinese TINA-TI 9.3.150.328SF-TI, Python 3.13.7**. Setup requires Python 3.11+ and checks the TINA executable version. Other versions/languages and a second physical computer remain unverified.

An interactive Windows desktop is required. Fourier provides only the native TDR plot; reliable harmonic coefficient export is not implemented. Noise support covers output amplitude spectral density. Encrypted factory macros require the native edit path. The simulator, vendor models/manuals/examples, personal settings and experiment data are not distributed.

## Validation

Completed on the release workstation:

- 68 public offline tests passed with no skips.
- Fresh setup in a separate data directory installed the pinned dependencies; all six installation/protocol checks passed and discovered 32 tools.
- The actual manifest/PowerShell launcher passed MCP initialization, tool discovery and synthetic UTF-8 numerical readback. A relocated copy under a Chinese/space-containing path and relative configuration/interpreter paths also passed.
- All 29 runtime files matched the validated 0.2.0 archive after LF normalization.

The source allowlist and release contents exclude personal settings, local paths, credentials, private experiments and vendor binaries/models. Per-file hashes and the adjacent archive checksum support verification; the build script can reproduce the ZIP from the same source and Python/zlib versions.

The normal Windows protocol checks passed. An initial attempt inside the authoring environment's restricted subprocess sandbox hung and was terminated; that is not counted as a successful integration test. No TINA process was started or circuit re-simulated for this packaging release. See [validation scope](docs/validation.md) for the historical real-TINA evidence and the distinction between the 75-test internal suite and 68-test public suite.

## Install

Extract `tina-bridge-0.2.2.zip`, retaining `.agents`, and follow [the installation guide](plugins/tina-bridge/README.md). The archive includes the complete public source and a per-file `package-index.json`. Verify its adjacent SHA-256 file before installation. The same content is available from the Git tag.

This is a GitHub/local-marketplace release; no OpenAI public-directory listing is claimed.
