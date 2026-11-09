"""Small installation check; --mcp lists tool schemas without operating TINA."""
import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'server'))
import settings


async def check_mcp(config):
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    env={'TINA_CONFIG':str(config)}
    for key in ('TINA_EXE','TINA_WORKSPACE','TINA_MONITOR','LOCALAPPDATA','USERPROFILE','PATH','SYSTEMROOT','TEMP','TMP'):
        if key in os.environ:env[key]=os.environ[key]
    server=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(ROOT/'server/mcp_entry.py')],cwd=str(ROOT/'server'),env=env)
    async with stdio_client(server) as (rd,wr):
        async with ClientSession(rd,wr) as client:
            initialized=await client.initialize();tools=await client.list_tools()
            return {'server':initialized.serverInfo.model_dump(),'tools':[t.name for t in tools.tools]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path);p.add_argument('--mcp',action='store_true');p.add_argument('--output',type=Path)
    a=p.parse_args();config=a.config.resolve() if a.config else settings.config_path()
    result={'plugin_root':str(ROOT),'config':str(config),'checks':{},'errors':[],
        'scope':'Files, version, Python dependencies and optional MCP schema discovery only; no TINA windows, circuit edits or solver runs.'}
    result['checks']['windows']=os.name=='nt'
    result['checks']['python_3_11_or_newer']=sys.version_info>=(3,11)
    result['python']={'executable':sys.executable,'version':sys.version.split()[0]}
    try:
        exe=settings.executable(path=config);version=settings.file_version(exe)
        result['tina']={'executable':exe,'file_version':version}
        result['checks']['supported_tina_version']=version==settings.SUPPORTED_VERSION
        result['workspace']=str(settings.workspace(config));result['monitor']=settings.monitor(config)
    except (OSError,ValueError) as error:result['errors'].append(str(error));result['checks']['supported_tina_version']=False
    dependencies={}
    for package in ('mcp','comtypes'):
        try:dependencies[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:dependencies[package]=None
    result['dependencies']=dependencies
    result['checks']['mcp_dependency']=dependencies['mcp']=='1.30.0'
    result['checks']['comtypes_dependency']=dependencies['comtypes']=='1.4.17'
    if a.mcp and all(result['checks'].values()):
        try:
            result['mcp']=asyncio.run(check_mcp(config))
            result['checks']['mcp_schema_discovery']='tina_sessions' in result['mcp']['tools']
        except Exception as error:result['errors'].append(str(error));result['checks']['mcp_schema_discovery']=False
    result['passed']=all(result['checks'].values()) and not result['errors']
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output:a.output.write_text(text+'\n',encoding='utf-8')
    print(text)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
