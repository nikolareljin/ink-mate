# Security and threat model

InkMate protects pairing and service credentials, voice and transcript content,
host workspace data, action authority, and firmware integrity. The physical
device, LAN, local service, providers, host executor, and approved local
workspaces are separate trust boundaries.

| Threat | Control |
| --- | --- |
| API impersonation | Unique device tokens, rotation, constant-time validation |
| Replay | Unique IDs, expiry, device binding, atomic single-use consumption |
| Untrusted response content | Response content cannot invoke executors; policy is authoritative |
| Command injection | Fixed executable/argument vectors; no shell parsing |
| Path escape | Canonical paths, traversal/symlink rejection, workspace allowlist |
| Accidental mutation | Explicit classification and physical confirmation |
| Proposal substitution | Bind exact operation, arguments, target, device, and expiry |
| Secret/privacy leakage | Environment indirection, redacted logs, short audio retention |
| Malformed input | Schema, type, duration, body, field, and response limits |
| Public exposure | Loopback default, LAN firewall, optional correctly configured TLS proxy |

Confirmation is a security boundary: the display shows the exact action and
target. Confirmation expires quickly and is consumed even if execution fails.

Residual risks remain. Plain HTTP lacks confidentiality against a LAN attacker.
A stolen paired device may authorize actions until revoked. Physical confirmation
cannot rescue an overbroad template. Host compromise defeats local controls.
E-paper retains visible data after power loss, so cards must avoid secrets.
