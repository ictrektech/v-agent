/** Container acceptance: real jailed runtimes, two identities, HTTP authentication. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { spawn, spawnSync } from 'node:child_process';
import { readFile, readdir } from 'node:fs/promises';

const base = 'http://127.0.0.1:8080';
const prefix = '/app/com.ictrek.v-agent';
const fixture = createServer((req, res) => {
  res.setHeader('content-type', 'application/json');
  if (req.url.includes('userinfo')) {
    const key = req.headers.authorization?.replace('Bearer ', '');
    if (!['fixture-a', 'fixture-b'].includes(key)) { res.end(JSON.stringify({ code: 10001 })); return; }
    res.end(JSON.stringify({ sub: key, preferred_username: key }));
  } else if (req.url === '/health') res.end(JSON.stringify({ fixture: 'image-studio' }));
  else res.end(JSON.stringify({ models: [{ id: 'fixture-model', qualified: 'fixture-model', name: 'Fixture model', kind: 'chat', endpoints: ['chat/completions'], capabilities: ['tools'] }] }));
});
fixture.listen(18090, '127.0.0.1'); await once(fixture, 'listening');
const gateway = spawn('/opt/v-agent/bin/entrypoint', [], {
  env: { ...process.env, VOS_OIDC_USERINFO_URL: 'http://127.0.0.1:18090/userinfo', V_SCHEDULER_URL: 'http://127.0.0.1:18090', IMAGE_STUDIO_BASE_URL: 'http://127.0.0.1:18090' },
  stdio: ['ignore', 'inherit', 'inherit'],
});
try {
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(base + '/__va/health')).ok) break; } catch { /* startup */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.equal((await fetch(base + prefix + '/api/agents')).status, 401);
  const logins = [];
  for (const access_token of ['fixture-a', 'fixture-b']) {
    const response = await fetch(base + prefix + '/__va/session');
    const { csrf } = await response.json();
    const result = await fetch(base + prefix + '/__va/auth', {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-va-csrf': csrf, cookie: 'va_csrf=' + csrf },
      body: JSON.stringify({ access_token, expires_in: 3600 }),
    });
    assert.equal(result.status, 200, 'a valid VOS subject must launch its runtime');
    const cookie = result.headers.getSetCookie().map(value => value.split(';')[0]).join('; ');
    const session = await (await fetch(base + prefix + '/__va/runtime-session', { headers: { cookie } })).json();
    assert.equal(session.subject, access_token);
    const me = await (await fetch(base + prefix + '/api/auth/me', { headers: { cookie, authorization: 'Bearer spoofed' } })).json();
    assert.equal(me.display_name, access_token, 'gateway must replace browser authorization');
    const html = await (await fetch(base + prefix + '/', { headers: { cookie } })).text();
    assert.match(html, /<title>v-agent/);
    assert.match(html, /\/app\/com\.ictrek\.v-agent\/assets\//);
    const agents = await (await fetch(base + prefix + '/api/agents', { headers: { cookie } })).json();
    assert.equal(agents.length, 1, 'V-Scheduler discovery must provision the default assistant');
    assert.equal(agents[0].name, 'v-agent');
    assert.equal(agents[0].state, 'running', agents[0].last_error ?? 'default assistant did not start');
    logins.push({ cookie, session });
  }
  assert.notEqual(logins[0].session.namespace, logins[1].session.namespace);
  assert.notEqual(logins[0].session.access_token, logins[1].session.access_token);
  const users = Object.values(JSON.parse(await readFile('/data/users.json', 'utf8')));
  const [a, b] = users;
  const read = spawnSync('runuser', ['-u', a.linuxName, '--', 'cat', `/data/users/${b.namespace}/.octop/octop.db`]);
  assert.notEqual(read.status, 0, 'another tenant database must be unreadable');
  const crossUser = await fetch(`http://127.0.0.1:${a.port}/api/auth/me`, {
    headers: { authorization: `Bearer ${logins[1].session.access_token}` },
  });
  assert.equal(crossUser.status, 401, 'another tenant token cannot authenticate directly to a runtime');
  const mcp = spawn('/opt/v-agent/bin/va-jail', [a.linuxName, String(a.uid), `/data/users/${a.namespace}`,
    '/usr/local/lib/v-agent/.venv/bin/python', '-c', `
import asyncio,json,sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable,args=['/usr/local/lib/v-agent/vos/mcp_server.py'])) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert any(t.name=='vos_api' for t in tools.tools)
            result=await session.call_tool('vos_api',{'service':'image-studio','method':'GET','path':'/health'})
            assert not result.isError
            payload=json.loads(result.content[0].text)
            assert payload['status']==200 and json.loads(payload['body'])['fixture']=='image-studio'
asyncio.run(main())
`], { env: { ...process.env, HOME: `/home/${a.namespace}` }, stdio: ['ignore', 'ignore', 'pipe'] });
  let mcpError = '';
  mcp.stderr.on('data', chunk => { mcpError += chunk; });
  const deadline = setTimeout(() => mcp.kill('SIGKILL'), 30000);
  const [mcpCode] = await once(mcp, 'exit');
  clearTimeout(deadline);
  assert.equal(mcpCode, 0, 'user-scoped MCP roundtrip: ' + mcpError);
  console.log('PASS: two VOS identities, real jailed runtimes, prefixed assets/API, forged-header replacement, private databases, automatic model setup and scoped MCP');
} catch (error) {
  for (const file of await readdir('/data/logs').catch(() => [])) {
    console.error('Isolated fixture runtime log:', await readFile('/data/logs/' + file, 'utf8'));
  }
  throw error;
} finally {
  gateway.kill('SIGTERM'); fixture.close();
}
