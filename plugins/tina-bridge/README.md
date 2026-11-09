# Install TINA Bridge

TINA Bridge provides MCP tools for AI clients such as Codex to read circuits, edit schematics, start simulations and retrieve results from TINA-TI. The AI calls the tools, the bridge operates TINA, and TINA solves the circuit.

You'll need Windows, TINA-TI and Python 3.11 or newer. The bridge was developed with the Simplified Chinese edition of TINA-TI 9.3. Get the simulator from [Texas Instruments](https://www.ti.com/tool/TINA-TI).

## 1. Set up the plugin

Download and extract the [release ZIP](https://github.com/escaper74/tina-bridge/releases/latest). In PowerShell, open the extracted root folder—the one containing `.agents` and `plugins`—and run:

```powershell
py -3 .\plugins\tina-bridge\setup.py --tina-exe '<full path to tina.exe>'
```

Replace the placeholder with the path to your installed `tina.exe`. If automatic discovery finds your installation, you can omit `--tina-exe` and its value. You can also use `python` in place of `py -3`.

Setup installs the Python dependencies and saves your TINA path under `%LOCALAPPDATA%\TinaBridge`.

## 2. Add it to Codex

From the same extracted root folder:

```powershell
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

Restart Codex and open a new chat. If you use the desktop Plugins UI, you can also select **TINA Bridge** from the local marketplace and install it there.

## 3. Try it on a circuit

Give Codex the path to a saved `.TSC` file and ask:

> Use TINA Bridge to open this circuit. List the components and explain how the output is connected.

Then try a change or a simulation:

> Change R1 to 2 kΩ, save it as a new circuit, and run a 20 ms transient simulation.

Use the component names and values that fit your circuit. Codex reads the project and calls the tools as it works. [More examples](references/quickstart.md).

## Check the connection

If the tools don't appear, run this from the extracted root folder:

```powershell
& "$env:LOCALAPPDATA\TinaBridge\venv\Scripts\python.exe" .\plugins\tina-bridge\check.py --mcp
```

A successful check lists 32 tools. If it reports an error, use the message to check the installation or settings:

| Message / symptom | What to check |
| --- | --- |
| TINA installation not found | Run setup again with `--tina-exe` pointing to the actual executable |
| Different executable version | Setup currently checks for `9.3.150.328SF-TI`; confirm which TINA installation you selected |
| Runtime is not installed | Run setup first, then check the `python` path in `settings.json` |
| Tools still missing after a successful check | Refresh the plugin installation, restart Codex and open a new chat |

## Use another MCP client

Setup prints the Python and settings paths. Use them in your client's local MCP configuration:

```json
{
  "mcpServers": {
    "tina_bridge": {
      "command": "<absolute path to runtime python.exe>",
      "args": ["-X", "utf8", "<absolute path to plugin/server/mcp_entry.py>"],
      "env": {"TINA_CONFIG": "<absolute path to settings.json>"}
    }
  }
}
```

For direct Codex MCP configuration, setup also writes a `codex-config.toml` snippet in the data directory. The [operating skill](skills/tina-bridge/SKILL.md) describes the usual circuit-editing and simulation workflow.

## Settings

Settings are in `%LOCALAPPDATA%\TinaBridge\settings.json`; snapshots, jobs and results go in its `runs` folder.

| Setting | Environment variable | Purpose |
| --- | --- | --- |
| `tina_exe` | `TINA_EXE` | TINA executable |
| `python` | `TINA_PYTHON` | Python used to launch the bridge |
| `workspace` | `TINA_WORKSPACE` | Folder for generated files and results |
| `monitor` | `TINA_MONITOR` | `secondary`, `unchanged`, or a Windows display name |

Environment variables override the settings file. `TINA_CONFIG` selects a different settings file.

Setup options:

- `--workspace '<folder>'`: choose where results are saved.
- `--monitor unchanged`: keep TINA windows on their current display.
- `--wheels '<folder>'`: install dependencies from an offline wheelhouse.
- `--data-dir '<folder>'`: put the Python environment and settings in a separate location. Set the client's `TINA_CONFIG` to that settings file, and pass `--config '<settings.json>'` when running the check.

To update, replace the plugin files, refresh the installation and restart the client. Run setup again when the dependency lock changes. Your saved settings and results live in the data directory.
