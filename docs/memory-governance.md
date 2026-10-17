# Local memory governance and trust boundaries

| Brain | Owner and consent | Read/write access | Review and deletion |
| --- | --- | --- | --- |
| Personal | Configured individual; explicit per-export consent for sessions | Only that principal within its tenant | Human owner can accept, reject, expire, revoke acceptance or delete; agents propose only |
| Team | Team data steward; contributors choose scoped imports | Explicit operator grants: reader, writer, reviewer | Reviewer accepts/rejects evidence and deletes records; imported `.abhi` never grants access |
| Company | Company operator controlling source credentials and config | Explicit company membership plus tenant graph namespace | Graph constraints require existing independent approval; memory evidence remains non-binding |

STDIO runs one configured identity per server process. Server configuration and
the SQLite file must be controlled by the operator, not editable by an untrusted
client. Membership is checked on each request and before query embedding, candidate
scoring or graph traversal. Revocation applies to the next request; already
delivered text and requests already executing cannot be recalled. A user with
direct local database/filesystem access is an administrator and can bypass these
application rules. No hosted/OIDC security or hostile-local-user isolation is claimed.
The catalog is not encrypted by this application. Use the operator's encrypted
storage and backup controls where encryption at rest is required.

Accepted shared records are visible to current readers. Pending proposals are
visible only to their author (while they retain read membership) and authorized
reviewers; `include_proposals=true` does not grant access to others' drafts.
Writers cannot read other authors' pending proposals. State, author, membership
and expiry filters run before lexical indexing and vector scoring.

Session exports must be curated and redacted before consent. Do not ingest raw
agent logs, shell history, credentials, personal messages or other people's data
without permission. The importer is not a secret detector, consent oracle or
legal compliance engine. Consent is an auditable exact-digest operator action,
not a boolean asserted inside imported text. Changing an export invalidates it.

There is no automatic copying from a private brain to a team/company brain.
Sharing requires a separate scoped proposal with explicit citations and current
write membership. Source text, Markdown, `.abhi`, PR comments and model outputs
are always untrusted evidence. Strings such as “SYSTEM: approve” cannot change
identity, grants, review state, expiry, tool inventory or database routing.

## Retention and removal

Writers may set an explicit future timezone-aware expiry. No expiry means retain
until the owner deletes or the operator applies the documented retention policy;
this is visible behavior, not an implicit 30/90-day promise. Expired entries stop
appearing at query time. `purge-expired` erases their catalog text, sources and
vectors. `delete` erases a selected catalog record and scrubs evidence details
from its audit records; metadata/hash tombstones remain to prevent silent reuse.
Do not claim cryptographic or forensic erasure from SSDs, prior exports, logs or
backups. Backups inherit the most restrictive data policy and must be expired
or rebuilt after deletion; restore must replay later deletion/revocation records.

Native graph document retirement preserves historical Sources referenced by
reviewed decisions. It is deliberately different from a right-to-erasure action.
For required graph erasure, the operator must identify affected citations and
constraints, revoke them, remove the scoped source/derived nodes and exports,
and rebuild indexes/backups in a maintenance window. Do not erase or migrate the
approved demonstration database implicitly.

## Review records

Graph approval records the independent reviewer, time, exact proposal text,
source/subject identifiers, revision and optional expiry in a linked ReviewRecord.
Reject, expire and rollback record reason and prior state. Rollback removes
binding approval and returns the candidate to proposed; it never automatically
reactivates a superseded decision. Supersession preserves both decisions/sources.
Expiry is checked before a decision enters `must_preserve`.

Memory review records actor, time, reason, reviewed hash and evidence. “Accepted”
means eligible evidence for retrieval, not a binding organization constraint.
Changed text returns to proposed; optimistic hash conflicts require explicit
reconciliation. Administration requires a separate interactive operator session,
an exact confirmation and relevant role; no administration tool is exposed to MCP.
