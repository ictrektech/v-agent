import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { identityFromPayload } from './vos-auth.mjs';
import { upsertUser } from './users.mjs';
import { signSession, verifySession, cookie, SESSION_COOKIE } from './session.mjs';
import { allowedImageRoute } from './apps.mjs';

test('identical display names never share a namespace, OS account, uid or runtime port', async () => {
  const root = await mkdtemp(join(tmpdir(), 'va-users-'));
  try {
    const a = identityFromPayload({ sub: 'subject-a', name: 'same' });
    const b = identityFromPayload({ sub: 'subject-b', name: 'same' });
    const records = await Promise.all([a, b].map(identity => upsertUser(join(root, 'users.json'), identity)));
    for (const field of ['namespace', 'linuxName', 'uid', 'port']) assert.notEqual(records[0].record[field], records[1].record[field]);
    const refreshed = await upsertUser(join(root, 'users.json'), { ...a, username: 'renamed' });
    assert.equal(refreshed.record.uid, records[0].record.uid);
    assert.equal(refreshed.record.namespace, a.namespace);
    assert.throws(() => identityFromPayload({ code: 10001, data: { sub: 'spoofed' } }));
  } finally { await rm(root, { recursive: true, force: true }); }
});
test('sessions reject tampering, expiration and another application secret', () => {
  const secret = Buffer.alloc(32, 1);
  const payload = { subject: 'a', namespace: 'a'.repeat(40), username: 'same', expiresAt: Date.now() + 60000 };
  const token = signSession(payload, secret);
  assert.equal(verifySession(token, secret).subject, 'a');
  assert.equal(verifySession(token + 'x', secret), undefined);
  assert.equal(verifySession(token, Buffer.alloc(32, 2)), undefined);
  assert.equal(verifySession(signSession({ ...payload, expiresAt: 1 }, secret), secret), undefined);
  assert.match(cookie(SESSION_COOKIE, token), /Path=\/app\/com\.ictrek\.v-octop\//);
});
test('image API capability rejects settings, host control and unrelated services', () => {
  assert.equal(allowedImageRoute('POST', '/api/v1/generate'), true);
  assert.equal(allowedImageRoute('GET', '/api/v1/jobs/a'), true);
  for (const path of ['/api/settings', '/api/admin', '/api/../settings', '/api/models/a/stop', '//evil/api/v1/jobs']) {
    assert.equal(allowedImageRoute('POST', path), false);
  }
});
