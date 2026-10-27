/** Per-user Image Studio API. A Unix socket grants only allowlisted app routes. */
import { createServer } from 'node:http';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { accessTokenFor } from './office.mjs';
import { runUserHelper } from './instances.mjs';
const servers = new Map();
const ORIGIN = process.env.IMAGE_STUDIO_BASE_URL ?? 'http://image-studio-backend:5000';
export function allowedImageRoute(method, path) {
  if (method === 'GET' && path === '/health') return true;
  if (method === 'DELETE') return /^\/api\/v1\/jobs\/[^/]+$/.test(path);
  if (method === 'GET') return /^\/api\/v1\/(about|me|models(?:\/[^/]+)?|jobs(?:\/[^/]+)?|outputs(?:\/[^/]+\/[^/]+)?|inputs(?:\/[^/]+)?)$/.test(path);
  return method === 'POST' && /^\/api\/v1\/(generate|inputs|models\/[^/]+\/pull|jobs\/[^/]+\/immich-upload)$/.test(path);
}
export async function ensureAppCapabilities(options) {
  if (servers.has(options.namespace)) return servers.get(options.namespace);
  const starting = (async () => {
    const socket = join(options.home, '.vagent', 'image-studio.sock');
    await unlink(socket).catch(error => { if (error.code !== 'ENOENT') throw error; });
    const server = createServer((req, res) => {
      void (async () => {
        const url = new URL(req.url, 'http://local');
        if (!allowedImageRoute(req.method, url.pathname)) { res.writeHead(403); res.end(); return; }
        const token = await accessTokenFor(options.namespace);
        if (!token) { res.writeHead(401); res.end(); return; }
        const abort = new AbortController(); res.once('close', () => abort.abort());
        const upstream = await fetch(`${ORIGIN}${url.pathname}${url.search}`, {
          method: req.method, headers: { authorization: `Bearer ${token}`, 'content-type': req.headers['content-type'] ?? 'application/json' },
          ...(req.method === 'GET' ? {} : { body: req, duplex: 'half' }), signal: abort.signal,
        });
        res.writeHead(upstream.status, { 'content-type': upstream.headers.get('content-type') ?? 'application/json', 'cache-control': 'no-store' });
        if (upstream.body) await pipeline(Readable.fromWeb(upstream.body), res); else res.end();
      })().catch(() => { if (!res.headersSent) res.writeHead(502); res.end(); });
    });
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(socket, resolve); });
    await runUserHelper(options.userHelper, ['claim', options.linuxName, socket]);
    return server;
  })();
  servers.set(options.namespace, starting);
  try { return await starting; } catch (error) { servers.delete(options.namespace); throw error; }
}
export async function closeAppCapabilities() {
  await Promise.allSettled([...servers.values()].map(async promise => { const server = await promise; server.close(); }));
  servers.clear();
}
