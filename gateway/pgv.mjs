/** Bootstrap stays in the root gateway. Agents receive only their own PGV role. */
import { spawn } from 'node:child_process';
export async function provisionPgv(record) {
  if (!process.env.PGV_BOOTSTRAP_PASSWORD) return;
  await new Promise((resolve, reject) => {
    const child = spawn('/usr/local/lib/v-octop/.venv/bin/python',
      ['/usr/local/lib/v-octop/vos/provision_pgv.py', record.namespace, String(record.uid)],
      { stdio: ['ignore', 'ignore', 'ignore'] });
    const timeout = setTimeout(() => child.kill('SIGKILL'), 15000);
    child.once('error', reject);
    child.once('exit', code => { clearTimeout(timeout); code === 0 ? resolve() : reject(new Error('PGV database provisioning unavailable')); });
  });
}
