# Extend InkMate

## Connect services on the host computer

The local adapter host is the bridge between InkMate and services that already
run on the same computer. Typical uses include a home-automation bridge, a
personal organizer, a local notes service, or a small status endpoint. It is
deliberately narrow: it listens on loopback only, does not expose a LAN API, and
never accepts a free-form shell command.

An integration can use one of two transports:

| Transport | Use it for | Boundary |
| --- | --- | --- |
| HTTP | A service listening on the same computer | `http://127.0.0.1`, `http://localhost`, or IPv6 loopback only |
| CLI | A local program with a stable invocation contract | Absolute executable path and optional absolute working directory |

The adapter host stores its database under `~/.local/state/inkmate/adapters`
and creates a private host token in ignored `.env` on first start. Run it in the
foreground with `./dev run adapter-host`, or install a systemd user service with
`./dev adapters install-service --start --yes`.

## Approval flow

1. A local service registers a versioned manifest and its HTTP endpoint or CLI
   command with the adapter host.
2. The host records it as `discovered` and prints a fingerprint.
3. Inspect it with `./dev adapters list`, then approve the exact fingerprint:

   ```sh
   ./dev adapters approve workflow FINGERPRINT --yes
   ./dev adapters grant workflow DEVICE_ID --yes
   ```

4. The integration becomes `active` only after the device grant. A changed
   manifest, endpoint, or command returns it to `discovered`, removes grants,
   and issues a new integration token after approval.

Use `./dev adapters revoke ID DEVICE_ID --yes` to remove one device grant,
`./dev adapters disable ID --yes` to stop an integration, and `./dev jobs` to
inspect retained accepted jobs.

## Adapter command reference

Run `./dev --help` for the complete command reference, parameters, and
activation example. This is the single source of truth for the local adapter
CLI. `list` prints each adapter ID, state, operations, and full SHA-256
fingerprint. `list` reports `active` only after both approval and a device
grant.

Copy the value after `SHA-256:` from `./dev adapters list`. It is a 64-character
hexadecimal fingerprint, not the adapter ID or a display name. This is a
made-up example. Do not reuse this value:

```text
$ ./dev adapters list
Adapter ID:  nikos-ubuntu-gedit
State:       discovered
SHA-256:     0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
Transport:   application
Operations:  app.open

$ ./dev adapters approve nikos-ubuntu-gedit 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef --yes
Approved adapter: nikos-ubuntu-gedit
Next: ./dev adapters grant nikos-ubuntu-gedit DEVICE_ID --yes

$ ./dev adapters grant nikos-ubuntu-gedit DEVICE_ID --yes
```

Replace the example SHA-256 value with the value printed on the local computer.
`NIKOS-GEDIT` and `nikos-ubuntu-gedit` are names, not fingerprints.
The command does not print the adapter token.

## Device adapter requests

The gateway maps a small set of fixed spoken requests to the JSON adapter
catalog. It does not ask the response provider to choose an executable. Every
desktop request returns a confirmation card; press BOOT briefly to launch or
hold BOOT to cancel.

| Adapter | Spoken requests | Typed request |
| --- | --- | --- |
| `nikos-vscode` | `open VSCode`, `open VS Code`, `could you open VS Code for me` | `adapter nikos-vscode app.open` |
| `nikos-browser` | `open browser` | `adapter nikos-browser browser.open` |
| `nikos-browser` | None | `adapter nikos-browser browser.open-url url=https://example.com` |
| OS text editor | `open text editor` | `adapter ADAPTER_ID app.open` |
| OS file explorer | `open files` | `adapter ADAPTER_ID app.open` |

The typed request format is `adapter ADAPTER_ID OPERATION_ID key=value`. Each
parameter must be declared by the operation. Browser URLs accept only absolute
`http` and `https` values. Text and file adapter IDs depend on the host OS; use
`./dev adapters list` for the exact IDs.

## Local adapter-host HTTP API

The host listens only on `127.0.0.1`. Administrative endpoints require
`Authorization: Bearer HOST_TOKEN`; the registration endpoint is local-only and
does not use that header. `HOST_TOKEN` is stored in the ignored `.env` file.

| Method and path | Parameters | Purpose |
| --- | --- | --- |
| `GET /healthz` | None | Host health check. |
| `POST /v1/registrations` | JSON `Registration` | Register an HTTP or CLI adapter as discovered. |
| `GET /v1/adapters` | Optional query `device_id` | List all adapters, or active adapters granted to one device. |
| `POST /v1/adapters/{ID}/approve` | Query `fingerprint` | Approve a discovered adapter definition. |
| `POST /v1/adapters/{ID}/grants/{DEVICE_ID}` | None | Grant a device access. |
| `DELETE /v1/adapters/{ID}/grants/{DEVICE_ID}` | None | Revoke a device grant. |
| `POST /v1/adapters/{ID}/disable` | None | Disable an adapter. |
| `GET /v1/jobs` | Optional query `device_id` | List accepted jobs. |
| `POST /v1/invocations` | JSON `Invocation` | Invoke an approved and granted adapter. The gateway normally calls this endpoint. |

## Providers

Speech and response providers use a typed interface and return normalized
results. A new provider needs health behavior, bounded timeouts, cancellation,
safe error mapping, and tests with mocked network calls. Keep secrets in the
environment and out of device responses and normal logs.

## Manifest and invocation contract

Every integration registers a versioned manifest. It declares a stable ID,
display name, transport, and one or more operations. Each operation declares
whether it is `read` or `mutating`, a one-to-thirty-second timeout, whether it
may return an accepted job, and an input schema. Input schemas accept only
declared string, integer, number, boolean, enum, or string-array parameters.

Approval prints a token for an HTTP integration. Keep it in local configuration
so the endpoint can verify host requests. Do not put it in a manifest or commit
it to a repository.

The gateway accepts only an explicit adapter request:

```text
adapter workflow work.next project=inbox
```

Parameters are checked against the operation schema before an integration runs.
Read operations return one short card. Changes require physical confirmation on
the device first. Accepted jobs are retained for seven days and can be listed
with `./dev jobs`.

## Desktop applications

The adapter host includes four fixed NikOS adapters per supported OS. They are
separate examples for adding other local applications without accepting an
executable path, arguments, or a shell command from InkMate.

Their primary definitions are the versioned JSON catalog at
`gateway/src/inkmate_gateway/nikos_applications.json`. Each entry supplies its
adapter ID, operating systems, fixed argument vector, and spoken aliases. The
adapter host validates and executes that catalog; application names and commands
are not accepted from a device request.

Approve and grant each adapter before use. `approve` asks the local operator
for confirmation. Add `--yes` only for an intentional non-interactive setup:

```sh
./dev adapters list
./dev adapters approve nikos-ubuntu-gedit FINGERPRINT
./dev adapters grant nikos-ubuntu-gedit DEVICE_ID --yes
```

Each launch is mutating and requires a short BOOT confirmation. Approve and
grant each adapter that the device may use.

| OS | Adapter | Spoken request | Fixed launcher |
| --- | --- | --- | --- |
| Ubuntu | `nikos-ubuntu-gedit` | `open text editor`, `open editor`, `open gedit` | `gedit` |
| Ubuntu | `nikos-ubuntu-files` | `open files` | `nautilus` |
| Ubuntu | `nikos-browser` | `open browser` | OS default browser |
| macOS | `nikos-macos-textedit` | `open text editor`, `open TextEdit` | `open -a TextEdit` |
| macOS | `nikos-macos-finder` | `open Finder`, `open files` | `open .` |
| macOS | `nikos-browser` | `open browser` | OS default browser |
| Windows | `nikos-windows-notepad` | `open text editor`, `open Notepad` | `notepad.exe` |
| Windows | `nikos-windows-files` | `open File Explorer`, `open files` | `explorer.exe` |
| Windows | `nikos-browser` | `open browser` | OS default browser |
| All three | `nikos-vscode` | `open coding IDE`, `open code`, `open VSCode` | `code`, or `open -a "Visual Studio Code"` on macOS |

The host registers only the adapters for its operating system. An unavailable
launcher returns an error card instead of reporting success.

The browser also has the explicit typed operation below for a specific URL. It
accepts absolute `http` and `https` URLs only, and still requires device
confirmation:

```text
adapter nikos-browser browser.open-url url=https://example.com
```

To add another NikOS application, define a new fixed adapter ID, its fixed
argument vector, spoken aliases, tests, and documentation. Do not add a generic
executable or argument parameter.

A CLI integration receives one JSON invocation on standard input and writes one
JSON result on standard output. HTTP integrations receive the same invocation at
`POST /v1/invoke` with their integration token. Both return `status`, `title`,
`body`, `severity`, and, for an accepted job, `job_id`. Results are bounded for
the e-paper card: title up to 32 characters and body up to 240 characters.

An HTTP registration has this shape. The host rejects non-loopback endpoints
and unknown fields.

```json
{
  "manifest": {
    "schema_version": "1",
    "adapter_id": "workflow",
    "version": "1.0.0",
    "display_name": "Workflow",
    "transport": "http",
    "operations": [{
      "operation_id": "work.next",
      "display_name": "Next work item",
      "mode": "read",
      "timeout_seconds": 5,
      "job_allowed": false,
      "input_schema": {
        "properties": {"project": {"type": "enum", "values": ["inbox"]}},
        "required": ["project"]
      }
    }]
  },
  "endpoint": "http://127.0.0.1:9001"
}
```

## Status sources

Status adapters are read-only. Keep payloads small and map them to card fields
rather than exposing arbitrary upstream JSON. Generic HTTP sources require an
explicit URL allowlist, authentication-by-environment, response size limits,
timeouts, and content-type validation.

## Actions

Actions are fixed executable plus argument templates, not command lines. Define
which arguments are constants, constrained values, or validated paths. Resolve
paths before checking workspace allowlists and reject symlink escapes. Mark all
state-changing actions as mutating so they require physical confirmation.

An integration may propose an action but cannot execute it directly. The central
service binds the proposal to a paired device, gives it a short expiry, and
consumes it once. Test denial, expiry, replay, target substitution, path
traversal, cancellation, and provider failure.

Job-oriented integrations remain disabled by default. Limit them to named
workspaces. Inspecting status may be read-only; starting or cancelling a job
requires confirmation.

## Cards

Prefer a new stable card kind only when an existing kind cannot represent the
information. Design for 200 x 200 monochrome output, concise copy, predictable
wrapping, and stale/offline state. Update schema fixtures and firmware layout
tests with every new kind.
