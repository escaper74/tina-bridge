# Validation scope

## Environment

The real-application evidence was collected on one Windows workstation with **Simplified Chinese TINA-TI 9.3.150.328SF-TI** and **Python 3.13.7**. The adapter requires a logged-in desktop. Installation migration on that workstation is not a second-computer test.

## Existing native validation (2026-11-06–07)

The public release preserves the content of the 29 runtime files from the 0.2.0 local package, with text line endings normalized to LF. Its original ZIP SHA-256 was `9c219c7d0ff0d13129b036d01612dff40910deba15874d66e95f1a6abd475203`. This identifies a historical local artifact, not the new public ZIP.

The maintained local evidence index recorded successful paths for structured circuit queries/comparison, native parameter and topology editing, source waveforms, discrete model selection, analyses and batch operation. Examples include an 8 V divider and a UA741 follower operating point near 0.99999 V. These are workflow checks, not generalized circuit-design certification.

An independent test used a separately extracted package and fresh MCP clients, without using the previous client's loaded tools:

- 32 tools discovered; 23 actual MCP calls completed without `isError`.
- Read a TPS40200 schematic and queried its connectivity.
- Changed external load R7 to 3.3 ohms and added a 33 ohm parallel branch.
- Saved and reopened the `.TSC`; both branches connected between VOUT and ground.
- Ran a real 0–1.5 ms transient; output mean over 1.3–1.5 ms was approximately **3.30797193 V**.
- Saved the owned documents and exited that independent TINA process normally.

The factory chip internals were not edited or replaced. This proves that particular edit/persistence/simulation chain, not every tool, all models, or all TPS40200 physical specifications. Private native exports, vendor models and detailed workstation logs are not redistributed here; this document is a public summary of the retained local evidence, not a substitute raw-data archive.

## Public offline suite

The original local suite reported 75 successful tests. Seven cases used archived native fixture files: one pin-map case, one macro operating-point case, three source-expansion cases and two TPS topology cases. Those private fixtures and dependent tests are excluded from this repository.

`scripts/run_tests.py` runs the remaining **68 self-contained cases** on Windows. It isolates configuration and temporary results, substitutes a harmless executable path only for import-time discovery, and never starts a simulator. It covers parsing, connectivity checks, routing, waveform validation, measurements, model-field validation, settings, analysis edge cases and persistent batch transitions with test doubles. It must not be interpreted as real TINA validation.

## Public release packaging checks

The release preparation verifies:

- Runtime SHA-256 equality with the 0.2.0 baseline after LF line-ending normalization.
- The public offline suite on the standalone tree.
- Setup in an isolated data directory and a real MCP initialization/list-tools check.
- The packaged PowerShell launcher and a relocated copy under a path containing Chinese characters and spaces, using synthetic UTF-8 waveform data.
- Two builds from the same source producing the same ZIP bytes, and file-index/archive checksums.
- The public allowlist for local paths, credentials, private experiment data and excluded vendor content.

The [release notes](../RELEASE_NOTES.md) report the checks actually completed. Packaging does not rerun the earlier chip experiments. A public-directory marketplace listing, a different TINA build/language, and independent installation on another computer are outside this release's verified scope.

## Known numerical boundaries

Fourier is a native TDR plot only. Text export does not supply reliable harmonic coefficients. Output-noise amplitude spectral density is validated; input/total noise and SNR transformations are not. Keep `job.json` alongside copied numerical noise exports so the reader can distinguish them from AC columns. Generic curve RMS is not integrated noise.

Per-signal sampling grids are preserved. Measurement windows and interpolation rules are returned explicitly. Circuit correctness and convergence still depend on the chosen model, inputs, solver settings and the physical question being tested.
