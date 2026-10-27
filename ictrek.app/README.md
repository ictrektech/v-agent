# v-agent on VOS

v-agent is the VOS edition of TencentCloud/Octop. The upstream Python package remains `octop`; product and VOS app names are `v-agent`. See `../UPSTREAM` for the fork base.

Open v-agent in VOS. OIDC Fastpath signs in silently. Each immutable VOS subject receives a separate Linux account, mount/PID jail, Octop process, database, experts, memory and workspace. Platform bearer/refresh tokens stay in gateway memory. The image requires mount/PID namespaces; startup fails if the jail cannot be created. Agent processes drop capabilities and cannot see other tenant homes. Networking is shared with the application container; upstream services still enforce their own permissions.

V-Scheduler models visible to the user are refreshed every minute. Chat Completions, Responses, Anthropic Messages, embedding and STT/TTS providers are configured automatically; completion-only models are excluded from the agent tool loop. No DeepSeek login or model API key is required. When several speech-recognition providers are exposed, choose the desired one in Voice settings; existing voice preferences are retained. A single discovered voice provider is selected automatically on first import. Model discovery does not prove that every upstream currently has resources available.

V-Office, AI Album, HybRAG, PhotoCraft and Image Studio are exposed through user-owned Unix sockets, bundled skills and the `vos-apps` MCP server. Their route allowlists preserve the current user's upstream permissions. Each target application must be installed and accept the `com.ictrek.v-agent` OIDC client where audience restrictions apply. Unavailable apps return explicit errors. Other third-party connectors retain their own authorization flows.

AI Album needs an operator to append `com.ictrek.v-agent` to its existing `IMMICH_VOS_AUDIENCE`. For library search/listing, include `asset.read,asset.statistics,album.read,person.read,user.read` in `IMMICH_VOS_PERMISSIONS`, retaining any existing permissions such as `asset.upload`. These keys still belong to the signed-in user; do not enable admin permissions or `asset.download`. Apply these settings through the album deployment configuration and restart its server. Its upload-only default intentionally returns 403 for read operations. Users then open v-agent without supplying album credentials. Preserve these settings when upgrading the album package.

The dashboard reads the installed VOS package version. Update checks use ictrektech/v-agent GitHub Releases; installation and upgrades are managed by the VOS App Store.

PhotoCraft uses its native MCP service through a per-user Unix socket, retaining the native document session across calls. Its skill discovers actual tool schemas before editing; v-harness-specific tool names are not assumed. Requires a PhotoCraft release exposing `/storage/mcp` (verified with 0.10.0-vos.4).

The V-Scheduler skill and MCP tools expose only inference: discover categories/endpoints, then invoke embeddings, ML, generation, speech, rerank or System One when the current catalog actually provides them. Generation/decision/search tabs show the actual user's Scheduler catalog. Empty categories stay empty; chat models are not substituted. Auto inherits image input from compatible visible chat candidates. Source metadata overrides remain owned by V-Scheduler.

PGV is optional. If installed, VOS injects its bootstrap password only into the root gateway. On first login the gateway provisions a separate non-superuser role and private database per immutable VOS subject, then installs a `VOS PGV` PostgreSQL storage connection in that user's runtime. Agents never receive the bootstrap credential. This adds a storage backend; it does not migrate the app's control database or replace file workspaces. Existing PGV databases and roles are not modified. If provisioning is unavailable the app still starts and reports that the managed PGV backend is unavailable.

## Build and release

Use architecture-matched hosts, after rsync from the local checkout to `~/dev/repos/v-agent`. Never run Git on build hosts. Run from a build copy under `~/dev/build`:

```sh
V_AGENT_SOURCE_REVISION=<local-commit> ./build_image.sh --target amd --sheet AMD_with_cuda,AMD_with_mxn100
V_AGENT_SOURCE_REVISION=<local-commit> ./build_image.sh --target arm --sheet ARM_with_cuda,ARM_without_cuda,l4t,thor_spark,SOPHON_bm1688
```

Images use only `swr.cn-southwest-2.myhuaweicloud.com/ictrek/v-agent`, with independent Feishu columns named `v-agent`. No v-harness image or column is modified. `ictrek.app/scripts/package.sh` resolves the published V-Scheduler version and validates the pull package.

Commit and push code directly to `main`; CI runs on main code pushes; a version-only release commit reuses the source checks. No PR or upstream develop/release branch is required. After pushing code and the VAI gitlink, run `ictrek.app/scripts/update_version.sh patch` locally. The `vos-v-agent-v*` workflow creates the public release and publishes to VOS App Store. Configure `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `APPSTORE_IP`, `APPSTORE_TOKEN`. The spreadsheet ID is fixed in code. Upstream desktop/PyPI publication workflows are retained as `.yml.upstream` and do not run for this product.
