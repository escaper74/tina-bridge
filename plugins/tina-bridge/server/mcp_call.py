r"""Call the actual stdio MCP server from a fresh client process.

Usage: .venv\Scripts\python.exe -X utf8 mcp_call.py --request request.json
request.json: {"tool":"tina_sessions","arguments":{}}
Use --list-tools for full schemas. This is also a protocol diagnostic fallback
when a host has not refreshed its MCP configuration yet.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def invoke(request=None):
    here=Path(__file__).resolve().parent
    env={k:os.environ[k] for k in ('TINA_EXE','TINA_WORKSPACE','TINA_MONITOR','TINA_CONFIG','TINA_PYTHON') if k in os.environ}
    server=StdioServerParameters(command=sys.executable,args=['-X','utf8',str(here/'mcp_entry.py')],
                                 cwd=str(here),env=env)
    async with stdio_client(server) as (rd,wr):
        async with ClientSession(rd,wr) as session:
            initialized=await session.initialize()
            if request is None:
                return {'server':initialized.model_dump(mode='json'),
                        'tools':[t.model_dump(mode='json') for t in (await session.list_tools()).tools]}
            result=await session.call_tool(request['tool'],request.get('arguments',{}))
            return result.model_dump(mode='json',exclude_none=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--request',help='UTF-8 JSON request file; - reads stdin')
    group.add_argument('--list-tools',action='store_true')
    args=parser.parse_args()
    request=None
    if args.request:
        text=sys.stdin.read() if args.request=='-' else Path(args.request).read_text(encoding='utf-8-sig')
        request=json.loads(text)
    result=asyncio.run(invoke(request))
    print(json.dumps(result,ensure_ascii=False))
    return 1 if result.get('isError') else 0


if __name__=='__main__':
    raise SystemExit(main())
