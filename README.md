# TINA Bridge

**Read, edit and simulate native TINA-TI circuits from an MCP client.**

TINA Bridge is a local Windows adapter for AI assistants and scripts. It works with the installed TINA application: reads components and connectivity, edits a copy of a `.TSC` schematic, runs the real solver, and returns numerical results and native result files. It includes a stdio MCP server and a Codex plugin with an operating skill.

[中文说明](README.zh-CN.md) · [Install](plugins/tina-bridge/README.md) · [Tool reference](docs/tools.md) · [Validation](docs/validation.md) · [Related work](docs/related-work.md)

## Compatibility

| Requirement | Supported / tested scope |
| --- | --- |
| OS | Windows with a logged-in interactive desktop |
| Simulator | **TINA-TI 9.3.150.328SF-TI, Simplified Chinese interface** |
| Python | 3.11 or newer required; **3.13.7 tested** |
| Transport | Local MCP over stdio |
| Client | Codex plugin or a client that can launch a local stdio server |

The installer checks the executable version and refuses other versions. Other TINA releases, English UI, macOS/Linux, and a second physical computer have **not** been validated. This is a desktop adapter, not a headless simulator or a TINACloud integration. Native dialogs can become visible.

Install TINA-TI separately from [Texas Instruments](https://www.ti.com/tool/TINA-TI). No simulator, vendor chip model, vendor manual, or third-party example circuit is included. No API key is required by the bridge; your AI client has its own requirements.

## Quick start

Download and extract the [latest release](https://github.com/escaper74/tina-bridge/releases/latest), including its hidden `.agents` directory, or clone this repository. In PowerShell, from the extracted repository root:

```powershell
py -3.13 .\plugins\tina-bridge\setup.py --tina-exe '<full path to installed tina.exe>'
& "$env:LOCALAPPDATA\TinaBridge\venv\Scripts\python.exe" .\plugins\tina-bridge\check.py --mcp
```

If TINA is found in its installer registration, PATH, or a standard install directory, omit `--tina-exe`. If your Python launcher has a different version, use that Python instead. Setup creates a virtual environment and settings under `%LOCALAPPDATA%\TinaBridge`; it does not edit your Codex configuration.

For Codex, register the extracted local marketplace:

```powershell
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

Refresh/restart the client and open a new chat. You can also install from the local marketplace in the desktop Plugins UI. The full [installation guide](plugins/tina-bridge/README.md) includes generic MCP configuration, isolated installs, offline wheels, and troubleshooting. This GitHub release is a repository/local-marketplace distribution; it is not an OpenAI public-directory listing.

Try this prompt, replacing the circuit path:

> Create your own TINA session and open my saved circuit. Read its components, pins and nets. Show me which components connect to the output. Do not change any values yet.

The first call should discover sessions; experiments should use their own process. For a numerical run, explicitly request the analysis interval and initial condition. Saving a copy, reopening it, and collecting actual solver output are separate operations.

## What it can do

The current interface exposes **32 MCP tools** and **15 native component templates**. [All tool names and their purpose](docs/tools.md) are documented; the runtime schema and `tina_catalog` supply the exact fields.

| Area | Implemented capabilities |
| --- | --- |
| Read circuits | Native XML and SPICE exports; components, values, positions, wires, nets, macro interfaces; component/net/pin queries and snapshot comparison |
| Edit native schematics | Add/remove components and wires; connect pins; rename, move, rotate and mirror; change external values; save to a new `.TSC` |
| Models | Insert locally installed `.TSM` macros; select existing D/Schottky/NPN/PNP/NMOS/PMOS library models; edit limited public instance fields |
| Sources | Native sine, square, single pulse and PWL configuration |
| Analyses | Transient, AC, DC sweep, operating point, temperature sweep, output-noise spectrum, Fourier native plot |
| Results | Native TDR files, supported numerical text exports, raw samples, time-weighted statistics, ripple, crossings, settling and other supported measurements |
| Experiments | Persistent batch manifests, reconnect/resume, parameter grids, seeded tolerance samples, local sensitivity cases and next-point boundary proposals |
| Sessions | Discover/create/status, circuit and result tabs, cancellation and orderly exit |

Connectivity comes from native exports, not inferred pixels. Normal operation uses process-bound Windows messages and accessibility controls; it does not use global mouse/keyboard input, clipboard transfers, or screenshot recognition. An active desktop is still required.

## Minimal tool workflow

The calls below show MCP tool names and arguments. Replace placeholders with **returned** PIDs and file paths; do not reuse a PID from an old session.

```text
tina_sessions({})
tina_create_session({})
tina_project({"pid": <returned PID>, "action": "open", "path": "<absolute circuit.TSC path>"})
tina_read_circuit({"pid": <returned PID>})
tina_query_circuit({"snapshot": "<returned snapshot path>", "component": "R1", "depth": 1})
tina_run_analysis({"pid": <returned PID>, "kind": "transient", "start": "0", "end": "10m", "initial": "zero"})
tina_job_status({"job_file": "<returned job_file>", "collect": true})
tina_read_result({"path": "<collected text path>"})
```

Poll the same job until it completes, and collect before starting another analysis in that process. Use actual signal names from the result. [Examples](plugins/tina-bridge/references/quickstart.md) include a native parameter edit and a two-case batch; [complete dictionary examples in Chinese](plugins/tina-bridge/references/usage.md) cover every analysis, experiment design and measurement field.

## Boundaries that matter

- **Encrypted macros:** TINA-TI 9.3 XML import can silently drop encrypted macros. The bridge rejects that edit path; use native `.TSC` editing for these circuits. Factory internals remain opaque and unchanged.
- **Fourier:** returns the native TDR plot, **not numerical harmonic coefficients**. The native text export is unsuitable for those coefficients.
- **Noise:** the validated result is the **output amplitude spectral density**. Input/total noise and SNR transformations are not supported; auxiliary `-phase` columns are not a noise phase.
- **Batch edits:** case operations currently support external parameters and existing PWL text. Prepare topology/model/waveform-type changes before freezing the baseline.
- **Waveforms:** `pulse` is one pulse; `square` is a bipolar 50% waveform about `dc_level`. Its `rise_fall` field is native tau; the full edge spans twice tau.
- **Solver settings:** saved TSC/XML values and the current analysis dialog can differ. Set and read back settings after opening the circuit.
- **Ownership:** operate only the selected or independently created session. Save owned pages before exit. The bridge is not a security sandbox for untrusted clients or circuit files.

## Evidence and development

Before public packaging, the bridge passed a 75-test local suite and several real TINA workflows. An independent extraction of version 0.2.0 completed 23 MCP calls: native load edits, a new parallel branch, save/reopen, a 0–1.5 ms TPS40200 transient and numerical readback. This is evidence of those workflows on one machine, not all TINA features or full chip validation. The public package preserves the runtime files from that validated baseline.

The public repository includes **68 self-contained offline tests**. Seven tests depending on private native exports are not included; the 75-test historical result is not presented as a fresh public-suite result. See [validation scope](docs/validation.md).

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\plugins\tina-bridge\server\requirements-lock.txt
& .\.venv\Scripts\python.exe .\scripts\run_tests.py
py -3.13 .\scripts\build_release.py
```

The offline test runner does not launch TINA or require its installation. The build uses an explicit file list, fixed ZIP metadata and SHA-256 checksums. See [rebuilding a release](docs/development.md). Changes should address real use cases; a full GUI automation framework is outside this adapter's scope.

## Positioning and license

TINA automation already exists: DesignSoft provides Python support and AI features in newer commercial TINA versions, and several open-source MCP servers target LTspice/ngspice. This project's contribution is a local, structured bridge for **native TINA-TI 9.3 engineering files**, including the native edit path needed to preserve opaque factory macros. Our search on 2026-11-09 found no directly equivalent public adapter within the searched sources; that is not a global uniqueness claim. [Research and primary sources](docs/related-work.md).

Project-authored code is released under the [MIT License](LICENSE). Dependencies and vendor assets retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). TINA and TINA-TI are names of their respective owners. This project is independent of DesignSoft, Texas Instruments and OpenAI.
