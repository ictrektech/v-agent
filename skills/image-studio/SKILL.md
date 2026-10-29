---
name: image-studio
description: Generate or edit images and videos through the current user's VOS Image Studio; inspect models, poll generation jobs, and download outputs without another login.
---

# Image Studio

Run `node /opt/v-octop/skills/image-studio/scripts/image-studio.mjs help` for exact arguments. This CLI uses the current user's capability socket; no API key or login is needed.

1. Inspect `models` and `model <key>` to select an installed model and supported parameters.
2. Submit `generate` with the requested prompt and model. Use `--input` only for a real downloaded reference file.
3. Poll with `wait <job-id>` until the job succeeds or fails. Report failures accurately.
4. Use `download <job-id>` to retrieve actual outputs. Copy each returned image `markdown` field verbatim into the reply body so the result appears inline. Provide video/file URLs as links.
5. Inspect the downloaded image with the available image-reading tool before describing its appearance. If the current model cannot read images, deliver the file and state that limitation without repeated attempts.
6. To save into the user's album, invoke the `album` skill's upload command with the downloaded file.

MCP callers can use `vos_api(service="image-studio", method="GET", path="/api/v1/models")` or POST `/api/v1/generate`. The CLI handles multipart uploads and binary downloads.

A 401 requires refreshing v-Octop's VOS session. A 403 means the route or current user is not authorized. A 502 means Image Studio is unavailable. Never claim a job succeeded without checking its terminal status and output.

After delivery, keep the answer brief and use the language of the user's latest question. Cancel only an unwanted unfinished job: `cancel` deletes the job and its outputs.
