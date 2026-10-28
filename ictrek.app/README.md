# v-Octop on VOS

v-Octop is the VOS edition of TencentCloud/Octop. The upstream Python package remains `octop`; product and VOS app names are `v-Octop`. See `../UPSTREAM` for the fork base.

Open v-Octop in VOS. OIDC Fastpath signs in silently. Each immutable VOS subject receives a separate Linux account, mount/PID jail, Octop process, database, experts, memory and workspace. Platform bearer/refresh tokens stay in gateway memory. The image requires mount/PID namespaces; startup fails if the jail cannot be created. Agent processes drop capabilities and cannot see other tenant homes. Networking is shared with the application container; upstream services still enforce their own permissions.

Chromium and its Linux dependencies are installed when the image is built, using the locked Playwright revision. Opening Workbench does not require a browser download. The shared browser binaries live read-only under `/usr/local/share/v-octop/browsers`; each VOS user keeps separate browser profiles in their own home.

V-Scheduler models visible to the user are refreshed every 10 seconds. Open model pages also refresh every 10 seconds while visible and when the window regains focus; refreshes preserve open configuration dialogs and the last successful model list during transient failures. HybRAG detection keeps its separate 60-second cadence. Chat Completions, Responses, Anthropic Messages, embedding and STT/TTS providers are configured automatically; completion-only models are excluded from the agent tool loop. No DeepSeek login or model API key is required. When several speech-recognition providers are exposed, choose the desired one in Voice settings; existing voice preferences are retained. A single discovered voice provider is selected automatically on first import. Model discovery does not prove that every upstream currently has resources available.

The Voice tab lists the current user's synchronized Scheduler services and the browser fallback. New knowledge-base configurations default to Scheduler embedding providers; select a model and save before indexing. Existing working local indexes retain their configuration until explicitly changed. The dashboard follows the VOS language snapshot and live language changes. Chat WebSockets and bundled avatar previews use the application's VOS URL prefix.

Existing generation, voice, decision, search and local embedding options remain available. V-Scheduler is an additional source; importing its models preserves existing vendor credentials, saved providers and selected defaults. The Decision tab keeps Jev, Microsoft, Laya and custom services alongside an independent V-Scheduler service. It selects native System One models, including Jev-compatible local Ollama models such as Tev1. Download local models through V-Scheduler's model management first. The selected qualified model ID and native decision requests pass through the current user's inference capability; vendor keys remain in V-Scheduler. Product MCP tools remain available in Craft mode when no optional third-party connectors are selected.

V-Office, AI Album, PhotoCraft and Image Studio are exposed through user-owned Unix sockets, bundled skills and the `vos-apps` MCP server. Their route allowlists preserve the current user's upstream permissions. Each target application must be installed and accept the `com.ictrek.v-octop` OIDC client where audience restrictions apply. Other third-party connectors retain their own authorization flows.

HybRAG uses one automatically managed native connector, replacing the duplicate WeKnora skill. It lists knowledge bases and documents, retrieves passages and reads documents through the current user's private socket. Tokens and active-area selection stay in the gateway; no API key or tenant ID is required. Missing HybRAG installations remain disconnected silently. Discovery repeats each minute, and the connector page refreshes automatically after installation. HybRAG area changes are picked up by the next token exchange within a minute. A manually disabled connector stays disabled.

AI Album needs an operator to append `com.ictrek.v-octop` to its existing `IMMICH_VOS_AUDIENCE`. For library search/listing, include `asset.read,asset.statistics,album.read,person.read,user.read` in `IMMICH_VOS_PERMISSIONS`, retaining any existing permissions such as `asset.upload`. These keys still belong to the signed-in user; do not enable admin permissions or `asset.download`. Apply these settings through the album deployment configuration and restart its server. Its upload-only default intentionally returns 403 for read operations. Users then open v-Octop without supplying album credentials. Preserve these settings when upgrading the album package.

Thinking and tool execution panels default to collapsed during generation as well as after completion; expand the process row to inspect details. Compact single-user turns show the latest answer instead of concatenating intermediate tool-round commentary. The existing chat menu can restore automatic expansion. Replies keep progress updates brief and focus on the result.

Replies follow the latest user message language, including switches within a conversation; an explicit output-language or translation request takes priority over UI locale and historical language preferences.

The dashboard reads the installed VOS package version. Update checks use ictrektech/v-agent GitHub Releases; installation and upgrades are managed by the VOS App Store.

PhotoCraft uses its native MCP service through a per-user Unix socket. Each expert resumes its own native session across the harness adapter's short-lived stdio processes. A private file lock serializes calls; session ids stay in the user's home and each request still receives that user's VOS authorization. `photocraft_import` transfers a selected workspace image as raw bytes and opens it; `photocraft_export` saves and downloads the edited document back to a chosen workspace file. Neither tool changes volume grants. Its skill discovers actual tool schemas before editing; v-harness-specific tool names are not assumed. Requires a PhotoCraft release exposing `/storage/mcp` (verified with 0.10.0-vos.4).

The V-Scheduler skill and MCP tools expose only inference: discover categories/endpoints, then invoke embeddings, ML, generation, speech, rerank or System One when the current catalog actually provides them. Generation/decision/search tabs show the actual user's Scheduler catalog. Empty categories stay empty; chat models are not substituted. Auto inherits image input from compatible visible chat candidates. Source metadata overrides remain owned by V-Scheduler.

PGV is optional. If installed, VOS injects its bootstrap password only into the root gateway. On first login the gateway provisions a separate non-superuser role and private database per immutable VOS subject, then installs a `VOS PGV` PostgreSQL storage connection in that user's runtime. Agents never receive the bootstrap credential. This adds a storage backend; it does not migrate the app's control database or replace file workspaces. Existing PGV databases and roles are not modified. If provisioning is unavailable the app still starts and reports that the managed PGV backend is unavailable.

## Build and release

Use architecture-matched hosts, after rsync from the local checkout to `~/dev/repos/v-octop`. Never run Git on build hosts. Run from a build copy under `~/dev/build`:

```sh
V_AGENT_SOURCE_REVISION=<local-commit> ./build_image.sh --target amd --sheet AMD_with_cuda,AMD_with_mxn100
V_AGENT_SOURCE_REVISION=<local-commit> ./build_image.sh --target arm --sheet ARM_with_cuda,ARM_without_cuda,l4t,thor_spark,SOPHON_bm1688
```

Images use only `swr.cn-southwest-2.myhuaweicloud.com/ictrek/v-octop`, with independent Feishu columns named `v-Octop`. No v-harness image or column is modified. `ictrek.app/scripts/package.sh` resolves the published V-Scheduler version and validates the pull package.

Commit and push code directly to `main`; CI runs on main code pushes; a version-only release commit reuses the source checks. No PR or upstream develop/release branch is required. After pushing code and the VAI gitlink, run `ictrek.app/scripts/update_version.sh patch` locally. The `vos-v-octop-v*` workflow creates the public release and publishes to VOS App Store. Configure `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `APPSTORE_IP`, `APPSTORE_TOKEN`. The spreadsheet ID is fixed in code. Upstream desktop/PyPI publication workflows are retained as `.yml.upstream` and do not run for this product.


GitHub Release publication and App Store distribution are separate jobs. Packaging verifies the current published V-Scheduler release through GitHub, independently of App Store availability. An App Store outage leaves the GitHub package available and marks only the store job as failed. Published assets are retained on retries.

To retry store distribution after maintenance, run `VOS Pull Package Release` manually with `publish_target=appstore` and `version=0.0.6` (or the required existing version). It downloads that exact GitHub asset; it does not rebuild images, repackage from newer Feishu rows, overwrite GitHub assets or bump the version. `publish_target=github` publishes only GitHub; the default `all` also attempts store distribution.
