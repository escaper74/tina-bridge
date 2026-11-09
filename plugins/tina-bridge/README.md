# Install TINA Bridge

This plugin runs a local stdio MCP server on Windows. It requires a separately installed **TINA-TI 9.3.150.328SF-TI** and an interactive desktop. Only the Simplified Chinese UI has been tested. The installer refuses other executable versions. Python 3.11+ is required; the validated interpreter is Python 3.13.7.

Get the simulator from [Texas Instruments](https://www.ti.com/tool/TINA-TI), under its own terms. This package contains no simulator or vendor chip models.

## Install the Python runtime

From this plugin directory (`plugins/tina-bridge`):

```powershell
py -3.13 .\setup.py --tina-exe '<full path to installed tina.exe>'
```

Use another installed Python 3.11+ if necessary. You can omit `--tina-exe` when discovery finds exactly one installation. Discovery checks installation registration, PATH and standard install directories, not the whole disk. Multiple installations require an explicit choice.

Setup creates `%LOCALAPPDATA%\TinaBridge\venv`, `settings.json`, and a `codex-config.toml` configuration **snippet**. It installs pinned Python dependencies from PyPI; it does not install TINA, modify PATH, or edit the client's configuration. For an existing wheelhouse, add `--wheels '<wheelhouse directory>'` to avoid package-index access.

Run the protocol check:

```powershell
& "$env:LOCALAPPDATA\TinaBridge\venv\Scripts\python.exe" .\check.py --mcp
```

It checks files, the executable version, dependencies and MCP tool discovery. It does not open TINA, edit a circuit or run a simulation. A successful check should list 32 tools. Actual circuit compatibility needs a read/edit-copy/save/reopen/solve test with your circuit.

## Connect Codex

Return to the repository or extracted release root, which contains `.agents/plugins/marketplace.json`:

```powershell
codex plugin marketplace add .
codex plugin add tina-bridge@tina-bridge
```

Refresh/restart the client and use a new chat. On clients exposing the local marketplace through the Plugins UI, choose **TINA Bridge** and install it there. If your CLI does not provide `plugin add`, use that UI or the direct MCP configuration below.

The package uses root `plugin.json`, `mcp.json` and `skills/` as described in [OpenAI's plugin packaging documentation](https://developers.openai.com/plugins/build/plugins). The distribution on GitHub is a local/repository marketplace, not an entry in OpenAI's universal public directory. Local-MCP public-directory submission has a separate approval process described in [desktop-only plugins](https://developers.openai.com/plugins/deploy/desktop-only).

## Connect another local MCP client

Use the Python path printed by setup and an absolute path to `server/mcp_entry.py`. Replace the placeholders in this generic configuration:

```json
{
  "mcpServers": {
    "tina_bridge": {
      "command": "<absolute path to runtime python.exe>",
      "args": ["-X", "utf8", "<absolute path to this plugin/server/mcp_entry.py>"],
      "env": {"TINA_CONFIG": "<absolute path to settings.json>"}
    }
  }
}
```

Forward slashes are convenient in Windows JSON paths. For a Codex version without plugins, merge the generated TOML snippet into your own MCP configuration. Direct MCP setup does not install the bundled skill; review `skills/tina-bridge/SKILL.md` for the operating workflow. Enable one connection route so you do not get duplicate tools. Other clients' end-to-end integrations are not part of the current validation.

## Settings and isolation

| Setting | Environment override | Meaning |
| --- | --- | --- |
| `tina_exe` | `TINA_EXE` | Installed executable |
| `python` | `TINA_PYTHON` | Python used by the plugin launcher |
| `workspace` | `TINA_WORKSPACE` | Generated snapshots, jobs and results |
| `monitor` | `TINA_MONITOR` | `secondary`, `unchanged`, or a Windows display name |

`TINA_CONFIG` selects a different settings file. Environment variables take precedence. Defaults are stored under `%LOCALAPPDATA%\TinaBridge`, and generated data goes in its `runs` directory. `--workspace` and `--monitor` can be passed to setup. Re-running setup preserves existing workspace/monitor choices when they are not overridden.

For an isolated installation, run `setup.py --data-dir '<separate directory>'`. Pass its resulting settings path to `check.py --config '<settings.json>' --mcp` and configure the client with the same `TINA_CONFIG`. The default plugin launcher will not automatically find a custom data directory.

## First use and troubleshooting

Read [minimal examples](references/quickstart.md) and [full dictionary examples (Chinese)](references/usage.md). Use `tina_catalog` and tool schemas before editing. Create an independent TINA session for experiments and save to new paths. Keep encrypted factory macros on the native editing route.

- **TINA not found:** pass `--tina-exe` to setup. A shortcut path is not an executable path.
- **Unsupported version:** use the validated installation. Another language or build needs adapter validation; changing the version constant alone does not establish compatibility.
- **Runtime is not installed:** run setup first; check `TINA_CONFIG` and `python` in the selected settings.
- **No tools:** run `check.py --mcp`, check the client's server stderr, refresh the marketplace/install and open a new chat.
- **Dialog/analysis needs attention:** inspect the returned state in the owned process. Do not repeatedly start another analysis or dismiss unsaved/overwrite prompts blindly.
- **Window appears in front:** some native dialogs still appear on the desktop. The default placement prefers a secondary monitor; this is not a headless service.

For upgrades, replace the repository/marketplace files, refresh the installation, then restart the client. Re-run setup if the dependency lock changes. Settings and results live outside the plugin cache. Uninstalling the plugin does not remove those data; retain any circuits and results you need.
