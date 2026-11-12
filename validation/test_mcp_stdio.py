"""Optional real stdio round-trip against a CPU-only canonical workflow stage."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'blender-character-short' / 'scripts'
HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install optional MCP dependency in an isolated test environment')
class StdioIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_roundtrip_reconnect_and_idempotent_submission(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'brief.json').write_text(json.dumps({'schema':1,'inputs':{},'user_exceptions':{'character_mmd':'User asks for no character in this fixture','scene':'User asks for no scene in this fixture'},'prompt':'A test of task orchestration only'}))
            project=root/'project.json'
            project.write_text(json.dumps({'schema':1,'id':'fixture','workflow_brief':'brief.json','workflow_report':'report.json'}))
            config=root/'config.json'
            config.write_text(json.dumps({'schema':1,'state_dir':str(root/'state'),'project_roots':[str(root)]}))
            params=StdioServerParameters(command=sys.executable,args=['-B',str(SCRIPTS/'mcp_service.py'),'--config',str(config)])
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    names={t.name for t in (await session.list_tools()).tools}
                    self.assertEqual(names,{'submit_job','job_status','job_logs','job_result','cancel_job'})
                    result=await session.call_tool('submit_job',{'project':str(project),'stage':'workflow','request_id':'protocol-fixture'})
                    self.assertFalse(result.isError)
                    state=result.structuredContent or json.loads(result.content[0].text)
                    if 'result' in state:state=state['result']
                    job=state['job_id']
                    for _ in range(100):
                        result=await session.call_tool('job_status',{'job_id':job})
                        state=result.structuredContent or json.loads(result.content[0].text)
                        if 'result' in state:state=state['result']
                        if state['status'] in ('completed','failed','uncertain'):break
                        await asyncio.sleep(.05)
                    self.assertEqual(state['status'],'completed')
            # Completed job remains queryable after service disconnect/reconnect.
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    for _ in range(100):
                        result=await session.call_tool('job_status',{'job_id':job})
                        state=result.structuredContent or json.loads(result.content[0].text)
                        if 'result' in state:state=state['result']
                        if state['status'] in ('completed','failed','uncertain'):break
                        await asyncio.sleep(.05)
                    self.assertEqual(state['status'],'completed')
                    before=(root/'report.json').read_bytes()
                    result=await session.call_tool('submit_job',{'project':str(project),'stage':'workflow','request_id':'protocol-fixture'})
                    self.assertFalse(result.isError)
                    self.assertEqual(before,(root/'report.json').read_bytes())
                    output=await session.call_tool('job_result',{'job_id':job})
                    self.assertFalse(output.isError)
                    await asyncio.sleep(.2)


if __name__=='__main__':unittest.main()
