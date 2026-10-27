---
name: vos-apps
description: Use VOS Image Studio to generate images, inspect models or retrieve generation jobs; discover the current user's VOS office, album and knowledge capabilities through MCP.
---

# VOS applications

Use the `vos_api` MCP tool. Credentials follow the current VOS user automatically.

| Service | Request |
|---|---|
| image-studio | GET `/api/v1/me`, GET `/api/v1/models`, GET `/api/v1/jobs` |
| image-studio | POST `/api/v1/generate` with the generation parameters supported by the selected model |
| voffice | GET `/api/v1/me`, GET `/api/v1/files` |
| album | GET `/users/me`, GET `/albums` |

For Image Studio, inspect model metadata before submitting a generation. Report the returned job ID and poll `/api/v1/jobs/<id>` until success or failure. Only describe generated images after retrieving the actual output.

For document uploads/downloads use the `voffice` skill. For album search and media transfers use `album`. For knowledge search and document reading use the automatically configured HybRAG connector.

A 401 requires refreshing v-Octop's VOS session. A 403 means the action is outside the capability or current user's permissions. A 502 means the application is unavailable; report which service failed. Never ask for another user's token or an administrator credential.
