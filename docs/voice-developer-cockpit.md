# Voice developer cockpit

InkMate v0.2.0 turns a confirmed spoken capture into a small, reviewable Markdown
work item inside an explicitly allowlisted local project. The device never writes
a work item, sends a GitHub request, or executes a host command merely because
speech recognition recognized a phrase.

## Configure

Set `INKMATE_WORK_ITEM_ROOT` to the common parent of configured projects. Map
project names to canonical local paths with `INKMATE_PROJECTS_JSON` and select
one `INKMATE_DEFAULT_PROJECT`. Each accepted capture is stored under
`.inkmate/captures/` in that project.

The gateway uses the configured local STT and LLM adapters to transcribe and
summarize. Submit an authenticated JSON request to `POST /v1/captures` with a
transcript and optional project; the device receives a confirmation card.
Confirm the returned action ID through the normal physical-confirmation route.
Only then is the Markdown item written.

## GitHub issues

Configure a fine-grained token with Issues read/write permission and map the
project to an `owner/repository` value. `POST /v1/work-items/{id}/issue`
creates a visible proposal. It creates an issue only after the device confirms
the proposal. Pull requests, merges, comments, reviewer changes, and arbitrary
GitHub writes are deliberately outside this release.

Keep the gateway on a trusted LAN, leave all credentials in ignored `.env`, and
do not enable coding-agent controls without an explicit later policy.
