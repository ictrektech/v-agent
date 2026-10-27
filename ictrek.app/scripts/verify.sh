#!/usr/bin/env bash
# Verify the local source on the configured Linux build host, without remote Git.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
HOST="${V_AGENT_CHECK_HOST:-tc232}"
STAMP_DIR="${V_AGENT_CHECK_STAMP_DIR:-${HOME}/dev/build/v-octop-delivery}"
mkdir -p "$STAMP_DIR"
digest="$(python3 - <<'PY'
from pathlib import Path
import hashlib, subprocess
h=hashlib.sha256()
paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z']).split(b'\0')
for name in sorted(set(paths)):
 if not name or name == b'ictrek.app/VERSION': continue
 p=Path(name.decode())
 if p.is_file(): h.update(name+b'\0'+p.read_bytes())
print(h.hexdigest())
PY
)"
if [[ -f "$STAMP_DIR/verified-source" && "$(cat "$STAMP_DIR/verified-source")" == "$digest" ]]; then
  echo 'v-octop: current source already passed the remote release checks.'
  exit 0
fi
rsync -az --delete --exclude=.git --exclude=.venv --exclude=node_modules --exclude=src/octop/dashboard --exclude=ictrek.app/dist ./ "$HOST:dev/repos/v-octop/"
ssh "$HOST" bash -s <<'REMOTE'
set -euo pipefail
mkdir -p "$HOME/dev/build/v-octop-check/source"
rsync -a --delete --exclude=.git --exclude=.venv --exclude=node_modules --exclude=src/octop/dashboard "$HOME/dev/repos/v-octop/" "$HOME/dev/build/v-octop-check/source/"
cd "$HOME/dev/build/v-octop-check/source"
# Reuse the locked dependency environment prepared on this build host.
export UV_NO_SYNC=1
make all PYTEST_JOBS=4
node --test gateway/*.test.mjs
.venv/bin/python -m compileall -q vos
for script in bin/entrypoint bin/va-jail bin/va-userctl bin/va-file build_image.sh ictrek.app/scripts/*.sh; do bash -n "$script"; done
cd dashboard
VITE_VOS=1 VITE_BASE_PATH=/app/com.ictrek.v-octop/ npm run build
docker run --rm --cpus=2 --memory=6g \
  --volume "$HOME/dev/build/v-octop-check/source:/work" --workdir /work/dashboard \
  --env NODE_OPTIONS=--max-old-space-size=4096 \
  swr.cn-southwest-2.myhuaweicloud.com/ictrek/node:22-bookworm-slim-amd \
  node node_modules/vitest/vitest.mjs run --maxWorkers=2 --minWorkers=1 \
  src/components/AuthGuard.test.tsx src/components/AuthGuard.vos.test.tsx \
  src/utils/vosSession.test.ts src/api/request.authToken.test.ts \
  src/api/request.unauthorized.test.ts src/hooks/useUnauthorizedRedirect.test.tsx \
  src/api/modules/wsChat.test.ts src/utils/vosLocale.test.ts
REMOTE
printf '%s\n' "$digest" > "$STAMP_DIR/verified-source"
