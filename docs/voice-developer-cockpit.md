# Voice capture workspace

InkMate can turn a confirmed spoken capture into a small, reviewable Markdown
work item inside a local project you explicitly allow. Speaking a phrase never
writes a file, sends a GitHub request, or runs a host command on its own.

## Set up a local workspace

Set `INKMATE_WORK_ITEM_ROOT` to the common parent of configured projects. Map
project names to canonical local paths with `INKMATE_PROJECTS_JSON` and select
one `INKMATE_DEFAULT_PROJECT`. Each accepted capture is stored under
`.inkmate/captures/` in that project.

The local service transcribes and summarizes the capture. Send an authenticated
JSON request to `POST /v1/captures` with a transcript and optional project; the
device receives a confirmation card. Only a physical confirmation writes the
Markdown item.

## Optional GitHub issue proposal

Configure a fine-grained token with Issues read/write permission and map the
project to an `owner/repository` value. `POST /v1/work-items/{id}/issue`
creates a visible proposal. It creates an issue only after the device confirms
the proposal. Pull requests, merges, comments, reviewer changes, and arbitrary
GitHub writes are deliberately outside this release.

Keep the service on a trusted LAN and leave credentials in ignored `.env`.
