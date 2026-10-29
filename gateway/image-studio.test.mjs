import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtempSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { spawn } from 'node:child_process';

// Exercise the actual CLI through a tenant socket, including raw image download.
test('Image Studio downloads bytes and supplies inline Markdown through the private socket', async () => {
  const home = mkdtempSync(join(tmpdir(), 'octop-img-'));
  mkdirSync(join(home, '.vagent'));
  const bytes = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0, 255]);
  const server = createServer((req, res) => {
    assert.equal(req.headers.authorization, undefined);
    if (req.url === '/api/v1/jobs/test-job') {
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify({ job_id: 'test-job', status: 'succeeded', outputs: ['output.png', 'clip.mp4'] }));
    } else {
      assert.match(req.url, /^\/api\/v1\/outputs\/test-job\/(output.png|clip.mp4)$/);
      res.end(bytes);
    }
  });
  try {
    await new Promise(done => server.listen(join(home, '.vagent/image-studio.sock'), done));
    const cli = resolve('skills/image-studio/scripts/image-studio.mjs');
    const result = await new Promise((done, fail) => {
      const child = spawn(process.execPath, [cli, 'download', 'test-job'], {
        cwd: home, env: { ...process.env, HOME: home, OCTOP_AGENT_ID: 'agent-one' },
      });
      let stdout = '', stderr = '';
      child.stdout.on('data', data => { stdout += data; });
      child.stderr.on('data', data => { stderr += data; });
      child.on('error', fail);
      child.on('close', code => code === 0 ? done(JSON.parse(stdout)) : fail(new Error(stderr)));
    });
    const [image, video] = result.files;
    assert.deepEqual(readFileSync(image.path), bytes);
    assert.match(image.markdown, /^!\[output.png\]\(\/api\/agents\/agent-one\/workspace\/download\?path=/);
    assert.equal(image.markdown, `![output.png](${image.url})`);
    assert.equal(video.markdown, undefined);
  } finally {
    await new Promise(done => server.close(done));
    rmSync(home, { recursive: true, force: true });
  }
});
