"""Install this plugin's Python runtime and local TINA settings; no Codex config edits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'server'))
import settings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tina-exe',type=Path,help='Installed tina.exe; otherwise use environment/config/discovery')
    p.add_argument('--data-dir',type=Path,default=settings.data_directory(),help='Runtime/config directory; defaults to LOCALAPPDATA/TinaBridge')
    p.add_argument('--workspace',type=Path,help='Generated snapshots and results directory')
    p.add_argument('--monitor',help='secondary, unchanged, or a Windows display name; preserves existing setting')
    p.add_argument('--wheels',type=Path,help='Optional offline wheel directory; pip uses --no-index')
    args=p.parse_args()
    if os.name!='nt' or sys.version_info<(3,11):raise SystemExit('Use Windows and Python 3.11 or newer. The tested interpreter is Python 3.13.')
    data=args.data_dir.resolve();config=data/'settings.json';prior=settings.read_config(config)
    exe=str(args.tina_exe.resolve()) if args.tina_exe else settings.executable(path=config)
    actual=settings.file_version(exe)
    if actual!=settings.SUPPORTED_VERSION:
        raise SystemExit(f'This adapter was validated with {settings.SUPPORTED_VERSION}; selected executable reports {actual}. No installation changes made.')
    data.mkdir(parents=True,exist_ok=True)
    runtime=data/'venv'
    if not (runtime/'Scripts/python.exe').is_file():venv.EnvBuilder(with_pip=True).create(runtime)
    python=runtime/'Scripts/python.exe'
    command=[str(python),'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'server/requirements-lock.txt')]
    if args.wheels:command.extend(['--no-index','--find-links',str(args.wheels.resolve())])
    subprocess.run(command,check=True)
    work=args.workspace.resolve() if args.workspace else settings.workspace(config)
    if not args.workspace and 'workspace' not in prior and not os.environ.get('TINA_WORKSPACE'):work=data/'runs'
    values={**prior,'tina_exe':exe,'python':str(python),'workspace':str(work),
            'monitor':args.monitor or prior.get('monitor','secondary')}
    # A prior configuration is small and user-editable; retain its exact bytes once.
    if config.exists():
        backup=config.with_suffix('.json.previous')
        if not backup.exists():backup.write_bytes(config.read_bytes())
    config.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    toml=lambda value:json.dumps(str(value),ensure_ascii=False)
    direct='\n'.join(['[mcp_servers.tina_bridge]',f'command = {toml(python)}',
        f'args = ["-X", "utf8", {toml(ROOT/"server/mcp_entry.py")}]',
        'startup_timeout_sec = 20','tool_timeout_sec = 3600','',
        '[mcp_servers.tina_bridge.env]',f'TINA_CONFIG = {toml(config)}',''])
    snippet=data/'codex-config.toml';snippet.write_text(direct,encoding='utf-8')
    print(json.dumps({'configured':True,'config':str(config),'python':str(python),'tina_version':actual,
        'direct_mcp_config_snippet':str(snippet),'next_check':[str(python),str(ROOT/'check.py'),'--config',str(config),'--mcp'],
        'codex_configuration_changed':False},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
