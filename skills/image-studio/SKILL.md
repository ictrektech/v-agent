---
name: image-studio
description: Generate or edit images and videos through the current user's VOS Image Studio; inspect models, poll generation jobs, and download outputs without another login.
---

# Image Studio

Run `node /opt/v-octop/skills/image-studio/scripts/image-studio.mjs help` for exact arguments. This CLI uses the current user's capability socket; no API key or login is needed.

1. Inspect `models` and `model <key>` to select an installed model and supported parameters.
2. Submit `generate` with the requested prompt and model. Use `--input` only for a real downloaded reference file.
3. Poll with `wait <job-id>` until the job succeeds or fails. Report failures accurately.
4. Use `download <job-id>` to retrieve actual outputs. Render returned image `url` values as Markdown images; provide video/file URLs as links.
5. To save into the user's album, invoke the `album` skill's upload command with the downloaded file.

MCP callers can use `vos_api(service="image-studio", method="GET", path="/api/v1/models")` or POST `/api/v1/generate`. The CLI handles multipart uploads and binary downloads.

A 401 requires refreshing v-Octop's VOS session. A 403 means the route or current user is not authorized. A 502 means Image Studio is unavailable. Never claim a job succeeded without checking its terminal status and output.
