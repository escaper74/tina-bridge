# Development and reproducible release

The source tree is also the installable repository marketplace:

```text
.agents/plugins/marketplace.json
plugins/tina-bridge/
  plugin.json
  mcp.json
  setup.py
  check.py
  scripts/launch.ps1
  server/                 # Python runtime and primitive metadata
  skills/tina-bridge/
  references/
tests/                    # Self-contained offline tests
scripts/
docs/
release-files.txt         # Explicit public distribution allowlist
```

## Offline checks

On Windows, create a development environment and install the same pinned dependencies used by setup:

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\plugins\tina-bridge\server\requirements-lock.txt
& .\.venv\Scripts\python.exe .\scripts\run_tests.py
```

The runner needs Windows libraries but no TINA installation or active session. It uses temporary configuration, a placeholder executable for module imports, and mocks for native operations. It does not launch the placeholder. To validate real TINA behavior, use a separately installed supported simulator and a new process; a passing unit suite is insufficient.

For the manifest/launcher smoke check, first complete plugin setup, then run:

```powershell
& "$env:LOCALAPPDATA\TinaBridge\venv\Scripts\python.exe" .\scripts\verify_plugin_runtime.py --plugin .\plugins\tina-bridge --config "$env:LOCALAPPDATA\TinaBridge\settings.json" --output .\build\protocol-check
```

Choose a new output directory. This sends real MCP initialize/list/read-result calls and checks Chinese text and relocation. The generated waveform is synthetic and is not a simulator result. Omit `--sessions` for the normal packaging check; that optional switch only discovers existing sessions and reads status, without editing or solving.

## Build a release

```powershell
py -3.13 .\scripts\build_release.py --output .\dist
py -3.13 .\scripts\build_release.py --output .\build\reproduction
Get-FileHash .\dist\tina-bridge-0.2.1.zip
Get-FileHash .\build\reproduction\tina-bridge-0.2.1.zip
```

The builder reads only `release-files.txt`; it never walks user data or copies an environment. The archive is UTF-8 text with stable file order, fixed ZIP timestamps/permissions and no workstation paths. It includes `package-index.json` with a SHA-256 and byte count for every listed file. Adjacent `.sha256` and `release-manifest.json` files describe the ZIP.

The builder normalizes text line endings to LF, so a Git checkout's newline policy does not change the archive. With identical source content and the same Python/zlib versions, two builds produce identical bytes. Different compression library versions may produce different ZIP bytes; the per-file SHA-256 values remain useful for content verification.

For a new release, update `plugin.json`, changelog/release notes, and the explicit allowlist. Review the actual listed files before publishing. Do not add executable installers, `.TSC`/`.TSM`/`.TDR` files, vendor models, personal settings, private logs, credentials or virtual environments. Third-party examples require their own redistribution permission; use original minimal examples where possible.

## Change scope and reports

Keep changes tied to an observed installation or engineering workflow problem. Report the Windows/TINA/Python versions, UI language, tool name, sanitized arguments and native error state. Use a minimal circuit you have permission to share. File paths, exported netlists and job records can contain private information.

Code contributions use the repository's MIT license. Preserve dependency notices. Test native changes in your own TINA process, save to new paths and keep factory macros opaque. Runtime changes require new relevant native evidence; documentation-only changes do not justify rerunning unrelated circuit experiments.
