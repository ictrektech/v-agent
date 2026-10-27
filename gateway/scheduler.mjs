/** Tenant-scoped inference proxy. VOS bearer tokens remain in the gateway. */
import { randomBytes } from 'node:crypto';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { accessTokenFor } from './office.mjs';

const ORIGIN = process.env.V_SCHEDULER_URL ?? 'http://v-scheduler:8080';
const keys = new Map();

/** Create one inference-only capability for a tenant process. */
export function schedulerEnvironment(namespace) {
  let key = keys.get(namespace);
  if (!key) { key = randomBytes(32).toString('hex'); keys.set(namespace, key); }
  return {
    VA_SCHEDULER_URL: `http://127.0.0.1:${process.env.PORT ?? 8080}/__va/scheduler`,
    VA_SCHEDULER_KEY: key,
  };
}

const normalized = value => String(value).trim().toLowerCase().replace(/^\/?(?:v1\/)?/, '').replaceAll('-', '_');

/** Select a supported wire API from declared endpoints, then capabilities. */
export function schedulerModels(payload) {
  if (!payload || !Array.isArray(payload.models)) throw new Error('Invalid V-Scheduler model catalog');
  const models = payload.models.flatMap(row => {
    const endpoints = (row.endpoints ?? []).map(normalized);
    const capabilities = (row.capabilities ?? []).map(normalized);
    let api;
    if (endpoints.some(e => ['chat', 'chat/completions', 'chat_completions'].includes(e))) api = 'openai-completions';
    else if (endpoints.some(e => ['responses', 'response'].includes(e))) api = 'openai-responses';
    else if (endpoints.some(e => ['messages', 'message', 'anthropic_messages', 'anthropic/messages'].includes(e))) api = 'anthropic-messages';
    else if (endpoints.some(e => ['completions', 'completion'].includes(e))) api = 'text-completions';
    else if (!endpoints.length && (capabilities.some(c => ['chat', 'completion', 'completions', 'generate', 'generation', 'tools', 'thinking'].includes(c))
      || !capabilities.length && ['chat', 'completion', 'completions'].includes(normalized(row.kind)))) api = 'openai-completions';
    // An upstream-routed model of undeclared kind is still a chat model: the
    // scheduler answers it through its upstream, so inference works even
    // though neither endpoints nor capabilities say anything usable.
    else if (!endpoints.length && !capabilities.length && normalized(row.kind) === 'unknown' && row.upstream_id) api = 'openai-completions';
    const id = row.qualified ?? row.id;
    if (!api || typeof id !== 'string' || !id) return [];
    const declared = row.input ?? row.input_modalities ?? row.modalities?.input ?? [];
    const values = [...(Array.isArray(declared) ? declared : []), ...capabilities].map(normalized);
    const image = values.some(value => ['vision', 'image', 'images', 'image_input', 'multimodal'].includes(value));
    return [{ id, name: row.name ?? id, api, input: image ? ['text', 'image'] : ['text'], virtual: row.virtual === true }];
  });
  // Auto routes the user's image requests to compatible visible candidates.
  const image = models.some(row => !row.virtual && row.input.includes('image'));
  return models.map(row => row.id === 'auto' && row.virtual && image ? { ...row, input: ['text', 'image'] } : row);
}

/** Fetch only models visible to this VOS user; management credentials are never used. */
export async function schedulerCatalog(token) {
  const response = await fetch(`${ORIGIN}/api/v1/models`, {
    headers: { authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`V-Scheduler model discovery: HTTP ${response.status}`);
  const payload = await response.json();
  const chat = new Map(schedulerModels(payload).map(row => [row.id, row]));
  return payload.models.map(row => {
    const id = row.qualified ?? row.id;
    const endpoints = (row.endpoints ?? []).map(normalized);
    const capabilities = (row.capabilities ?? []).map(normalized);
    const categories = [];
    if (chat.has(id)) categories.push('chat');
    if (endpoints.includes('embeddings')) categories.push('embedding');
    if (endpoints.some(e => ['images/generations', 'images/edits', 'videos/generations', 'audio/music/generations'].includes(e))) categories.push('generation');
    if (endpoints.some(e => e.startsWith('audio/')) && !endpoints.includes('audio/music/generations')) categories.push('voice');
    if (endpoints.includes('systemone') || capabilities.includes('decision')) categories.push('decision');
    if (endpoints.some(e => ['search', 'web/search'].includes(e))) categories.push('search');
    return { id, name: row.name ?? id, kind: row.kind, endpoints, capabilities, categories,
      ...(chat.get(id) ?? {}) };
  });
}

/** Authenticate a process capability and forward only model discovery and inference. */
export async function handleScheduler(req, res, path) {
  const target = new URL(path, 'http://localhost');
  path = target.pathname;
  const key = req.headers.authorization?.replace(/^Bearer /, '') ?? req.headers['x-api-key'];
  const namespace = [...keys].find(([, value]) => value === key)?.[0];
  const reply = (status, data) => {
    res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify(data));
  };
  if (!namespace) return reply(401, { error: { message: 'Invalid inference capability' } });
  const token = await accessTokenFor(namespace);
  if (!token) return reply(401, { error: { message: 'VOS session expired; refresh v-agent' } });
  if (req.method === 'GET' && path === '/v1/models') return reply(200, { data: (await schedulerCatalog(token)).filter(row => row.categories.includes('chat')) });
  if (req.method === 'GET' && path === '/catalog') return reply(200, { models: await schedulerCatalog(token) });
  const post = ['/v1/chat/completions', '/v1/responses', '/v1/messages', '/text/v1/chat/completions',
    '/v1/embeddings', '/v1/rerank', '/v1/ml/predictions', '/v1/systemone',
    '/v1/images/generations', '/v1/images/edits', '/v1/images/variations', '/v1/videos/generations',
    '/v1/audio/transcriptions', '/v1/audio/translations', '/v1/audio/speech', '/v1/audio/music/generations'];
  const read = /^\/v1\/(?:images|videos)\/[^?]+$/.test(path) ||
    ['/v1/audio/voices', '/v1/audio/speakers'].includes(path);
  if (!(req.method === 'POST' && post.includes(path) || req.method === 'GET' && read)) {
    return reply(403, { error: { message: 'Inference route not allowed' } });
  }
  if (path === '/text/v1/chat/completions') return forwardTextCompletion(req, res, token);
  const abort = new AbortController();
  res.once('close', () => abort.abort());
  const response = await fetch(`${ORIGIN}${path}${target.search}`, {
    method: req.method, headers: {
      authorization: `Bearer ${token}`, 'content-type': req.headers['content-type'] ?? 'application/json',
      ...(req.headers['anthropic-version'] ? { 'anthropic-version': req.headers['anthropic-version'] } : {}),
      ...(req.headers['anthropic-beta'] ? { 'anthropic-beta': req.headers['anthropic-beta'] } : {}),
    }, ...(req.method === 'GET' ? {} : { body: req, duplex: 'half' }), signal: abort.signal,
  });
  res.writeHead(response.status, { 'content-type': response.headers.get('content-type') ?? 'application/json', 'cache-control': 'no-store' });
  if (response.body) await pipeline(Readable.fromWeb(response.body), res);
  else res.end();
}

/** Adapt text-only completion models to the chat transport; tools remain unsupported. */
async function forwardTextCompletion(req, res, token) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > 16 * 1024 * 1024) { res.writeHead(413); res.end(); return; }
    chunks.push(chunk);
  }
  const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const prompt = body.messages.map(message => `${message.role}: ${typeof message.content === 'string' ? message.content : JSON.stringify(message.content)}\n`).join('') + 'assistant:';
  const abort = new AbortController();
  res.once('close', () => abort.abort());
  const response = await fetch(`${ORIGIN}/v1/completions`, {
    method: 'POST', headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify({ model: body.model, prompt, stream: body.stream, max_tokens: body.max_tokens ?? body.max_completion_tokens, temperature: body.temperature, top_p: body.top_p, stop: body.stop }),
    signal: abort.signal,
  });
  if (!response.ok) {
    res.writeHead(response.status, { 'content-type': 'application/json' });
    res.end(await response.text()); return;
  }
  const convert = (value, stream) => ({ ...value, object: stream ? 'chat.completion.chunk' : 'chat.completion', choices: value.choices.map(choice => ({
    index: choice.index, finish_reason: choice.finish_reason,
    [stream ? 'delta' : 'message']: { role: 'assistant', content: choice.text ?? '' },
  })) });
  if (!body.stream) {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(convert(await response.json(), false))); return;
  }
  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-store' });
  let pending = '';
  const decoder = new TextDecoder();
  for await (const chunk of response.body) {
    pending += decoder.decode(chunk, { stream: true }).replaceAll('\r\n', '\n');
    let split;
    while ((split = pending.indexOf('\n\n')) !== -1) {
      const event = pending.slice(0, split); pending = pending.slice(split + 2);
      const data = event.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trim()).join('\n');
      if (!data) continue;
      res.write(`data: ${data === '[DONE]' ? data : JSON.stringify(convert(JSON.parse(data), true))}\n\n`);
    }
  }
  res.end();
}
