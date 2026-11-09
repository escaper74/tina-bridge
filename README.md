# TINA Bridge

**Let Codex read your TINA circuit, edit it, and run the simulation.**

TINA Bridge connects your AI assistant to TINA-TI on Windows. Tell it what you want to change or measure, and it can work on the schematic, run analyses, and read back the results. Your circuit stays a `.TSC` file that you can open and continue editing in TINA.

[中文](README.zh-CN.md) · [Download](https://github.com/escaper74/tina-bridge/releases/latest) · [Installation](plugins/tina-bridge/README.md)

## What can I ask it to do?

> Open this TSC file and explain how the output and feedback loop are connected.

> Change R1 to 2 kΩ, save a new copy, and run a 20 ms transient simulation.

> Try load resistances of 1 kΩ, 2 kΩ and 4 kΩ, then compare the output voltage and ripple.

You give the task in plain language. The assistant uses the plugin's tools to carry it out in TINA.

| Task | What the bridge provides |
| --- | --- |
| Understand a circuit | Read components, values, pins and nets; follow connections and compare two circuit versions |
| Edit a schematic | Add or remove components and wires, connect pins, move or rotate parts, change values and save the result |
| Set up sources and models | Configure sine, square, pulse and PWL sources; insert local macros and select library device models |
| Run simulations | Transient, AC, DC sweep, operating point, temperature sweep, output-noise spectrum and Fourier plots |
| Read the results | Get waveform samples, average/RMS values, ripple, overshoot, settling time and threshold crossings |
| Compare several cases | Run parameter sweeps, tolerance samples and sensitivity studies, with saved results for each case |

## Install

You'll need **Windows, TINA-TI, Python 3.11+ and Codex**. This bridge was developed with the **Simplified Chinese edition of TINA-TI 9.3**.

1. Install [TINA-TI](https://www.ti.com/tool/TINA-TI) if you haven't already.
2. Download the ZIP from [Releases](https://github.com/escaper74/tina-bridge/releases/latest) and extract the whole folder, including `.agents`.
3. Open PowerShell in that folder and run:

```powershell
py -3 .\plugins\tina-bridge\setup.py --tina-exe '<full path to tina.exe>'
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

Replace the path with your installed `tina.exe`. If setup can find TINA automatically, you can leave out `--tina-exe` and its value.

Restart Codex, start a new chat, and give it a `.TSC` file and a task. For a first try:

> Use TINA Bridge to open this circuit and list its components and connections.

You can also give Codex this repository and ask it to follow the [installation guide](plugins/tina-bridge/README.md). That guide includes a connection check and configuration for other MCP clients.

## How it works

The plugin runs a local MCP server that talks to the installed TINA application. It reads TINA's circuit exports, operates the schematic editor and analysis dialogs, and collects the solver's output. Edits are saved as new circuit files, and simulation data is kept on your computer.

The interface includes 32 tools and 15 native component templates. For scripted use, see the [tool reference](docs/tools.md) and [MCP examples](plugins/tina-bridge/references/quickstart.md).

## More information

- [Installation and settings](plugins/tina-bridge/README.md)
- [Chinese circuit-editing guide](docs/reference.zh-CN.md)
- [Analysis and measurement details](docs/analyses.zh-CN.md)
- [Tests and TINA examples](docs/validation.md)
- [Development and release builds](docs/development.md)
- [Related projects](docs/related-work.md)

[MIT License](LICENSE) · [Third-party notices](THIRD_PARTY_NOTICES.md)
