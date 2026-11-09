"""Check the packaged launcher and its relocated copy over real MCP stdio."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client


async def exercise(root,config,wave,inspect_sessions=False):
    entry=json.loads((root/'mcp.json').read_text(encoding='utf-8'))['mcpServers']['tina_bridge']
    replace=lambda text:text.replace('${PLUGIN_ROOT}',str(root))
    env={key:os.environ[key] for key in ('PATH','SYSTEMROOT','USERPROFILE','LOCALAPPDATA','TEMP','TMP') if key in os.environ}
    env['TINA_CONFIG']=str(config)
    params=StdioServerParameters(command=entry['command'],args=[replace(x) for x in entry['args']],cwd=replace(entry['cwd']),env=env)
    async with stdio_client(params) as (rd,wr):
        async with ClientSession(rd,wr) as client:
            init=await client.initialize();names=[tool.name for tool in (await client.list_tools()).tools]
            result=await client.call_tool('tina_read_result',{'path':str(wave),'signal':'输出电压 (V)'})
            if result.isError:raise AssertionError(result)
            data=result.structuredContent
            if data['name']!='输出电压 (V)' or data['x']!=[0.0,1.0] or data['y']!=[0.0,1.0]:raise AssertionError(data)
            record={'server':init.serverInfo.model_dump(),'tools':names,'utf8_result':data,
                    'launcher':params.model_dump(),'passed':True}
            if inspect_sessions:
                sessions=await client.call_tool('tina_sessions',{})
                if sessions.isError:raise AssertionError(sessions)
                record['sessions']=sessions.structuredContent
                pids=[item['pid'] for item in sessions.structuredContent['sessions']]
                if pids:
                    status=await client.call_tool('tina_status',{'pid':pids[0]})
                    if status.isError:raise AssertionError(status)
                    record['status']=status.structuredContent
                    if record['status']['pid']!=pids[0]:raise AssertionError(record['status'])
            return record


async def verify(root,config,output,inspect_sessions=False):
    output.mkdir(parents=True,exist_ok=False)
    wave=output/'中文波形.txt';wave.write_text('*时间 (s)\t*输出电压 (V)\n0\t0\n1\t1\n',encoding='utf-8')
    original=await asyncio.wait_for(exercise(root,config,wave,inspect_sessions),timeout=45)
    print('Original packaged launcher passed',flush=True)
    relocated=output/'迁移后的 插件';shutil.copytree(root,relocated,ignore=shutil.ignore_patterns('__pycache__'))
    moved=await asyncio.wait_for(exercise(relocated,config,wave,inspect_sessions),timeout=45)
    settings=json.loads(config.read_text(encoding='utf-8-sig'))
    relative=None
    if Path(settings['python']).drive.casefold()==relocated.drive.casefold():
        settings['python']=os.path.relpath(settings['python'],relocated)
        (relocated/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
        relative=await asyncio.wait_for(exercise(relocated,Path('settings.json'),wave),timeout=45)
    record={'passed':True,'scope':'Real MCP launch/list/read-result, optional read-only sessions/status; no TINA window changes or solver operations',
            'original':original,'relocated':moved,'same_tool_set':original['tools']==moved['tools'],
            'relative_config_and_python':relative,'cross_machine_test':False}
    (output/'evidence.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':record['passed'],'same_tool_set':record['same_tool_set'],'tools':len(original['tools']),
                      'evidence':str(output/'evidence.json')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plugin',type=Path,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sessions',action='store_true',help='Also query existing TINA sessions and one process status, without changing any windows')
    a=p.parse_args();asyncio.run(verify(a.plugin.resolve(),a.config.resolve(),a.output.resolve(),a.sessions))
