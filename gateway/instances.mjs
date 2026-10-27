/** One jailed Octop process and persistent home per verified VOS subject. */
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { schedulerEnvironment } from './scheduler.mjs';
import { provisionPgv } from './pgv.mjs';

const instances = new Map();
const JAIL = process.env.JAIL_BIN ?? '/opt/v-octop/bin/va-jail';
export function userPaths(dataRoot, namespace) {
  const home = join(dataRoot, 'users', namespace);
  return { home, workspace: join(home, 'workspace'), runtime: join(home, '.vagent', 'runtime-token') };
}
export async function runUserHelper(helper, args) {
  await new Promise((resolve, reject) => {
    const child = spawn(helper, args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let detail = '';
    child.stderr.on('data', chunk => { detail += chunk; });
    child.once('error', reject);
    child.once('exit', code => code === 0 ? resolve() : reject(new Error(`user helper (${code}): ${detail}`)));
  });
}
export async function ensureInstance(options) {
  const { record, dataRoot, userHelper } = options;
  const old = instances.get(record.namespace);
  if (old?.starting) return old.starting;
  if (old?.child && old.child.exitCode === null && !old.child.killed) {
    old.cookie = (await readFile(userPaths(dataRoot, record.namespace).runtime, 'utf8')).trim();
    return old;
  }
  const entry = { port: record.port, child: undefined, cookie: undefined };
  const starting = (async () => {
    const paths = userPaths(dataRoot, record.namespace);
    await runUserHelper(userHelper, ['ensure', record.linuxName, String(record.uid), paths.home]);
    await provisionPgv(record).catch(() => console.warn("PGV provisioning unavailable; this user has no managed PGV backend yet"));
    await mkdir(join(dataRoot, 'logs'), { recursive: true, mode: 0o700 });
    await rm(paths.runtime, { force: true });
    const home = `/home/${record.namespace}`;
    const child = spawn(JAIL, [record.linuxName, String(record.uid), paths.home,
      '/usr/local/lib/v-octop/.venv/bin/python', '/usr/local/lib/v-octop/vos/runtime.py'], {
      env: { HOME: home, OCTOP_HOME: `${home}/.octop`, VA_PORT: String(record.port),
        VA_DISPLAY_NAME: record.username, VA_USERNAME: record.username, VA_SUBJECT: record.subject,
        VOS_APP_VERSION: process.env.VOS_APP_VERSION ?? "unknown", VA_SKILLS_DIR: '/opt/v-octop/skills',
        PLAYWRIGHT_BROWSERS_PATH: '/usr/local/share/v-octop/browsers',
        PATH: '/usr/local/lib/v-octop/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin',
        LANG: 'C.UTF-8', LC_ALL: 'C.UTF-8', ...schedulerEnvironment(record.namespace) },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    entry.child = child;
    const log = createWriteStream(join(dataRoot, 'logs', `${record.namespace}.log`), { flags: 'a', mode: 0o600 });
    child.stdout.pipe(log, { end: false }); child.stderr.pipe(log, { end: false });
    let spawnError;
    child.once('error', error => { spawnError = error; });
    child.once('exit', () => { log.end(); if (instances.get(record.namespace) === entry) instances.delete(record.namespace); });
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      if (spawnError) throw spawnError;
      if (child.exitCode !== null) throw new Error(`v-Octop runtime exited (${child.exitCode}); inspect tenant log`);
      try {
        const token = (await readFile(paths.runtime, 'utf8')).trim();
        const ready = await fetch(`http://127.0.0.1:${record.port}/api/health`, { signal: AbortSignal.timeout(1000) });
        if (token && ready.ok) { entry.cookie = token; entry.starting = undefined; return entry; }
      } catch { /* Runtime writes its token only after initialization. */ }
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    child.kill('SIGTERM');
    throw new Error('v-Octop runtime start timed out');
  })();
  entry.starting = starting;
  instances.set(record.namespace, entry);
  try { return await starting; } catch (error) { entry.child?.kill('SIGTERM'); instances.delete(record.namespace); throw error; }
}
export function liveInstance(namespace) { return instances.get(namespace); }
export async function stopAll() {
  for (const instance of instances.values()) instance.child?.kill('SIGTERM');
  instances.clear();
}
