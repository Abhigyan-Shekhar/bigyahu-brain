# .abhi interchange

## Version 2: selected current-memory graphs

`.abhi/2` exports a bounded graph slice from explicitly selected, current,
accepted memory records. It preserves shared citation and code-identifier
topology. Version 1 imports remain supported without conversion or migration.

The base envelope has exactly `format`, `tenant`, `team`, `collection`,
`parent_digest`, `records`, `graph` and `digest`. `format` is `abhi/2`.
An assertion-bearing file additionally has the optional `relations` array
described below; other fields remain forbidden.
Records have the same content fields as version 1 below, with opaque portable IDs
matching `r-` plus 64 lowercase hexadecimal characters. IDs remain stable after
import and re-export; they do not authenticate authorship or anonymize source text.
Initial exports use empty `parent_digest` and per-record `expected_hash`.

`graph` has exactly two arrays, `nodes` and `edges`, in canonical sorted order:

| Node kind | Exact fields | Identity |
| --- | --- | --- |
| Memory | `id`, `kind`, `record` | The selected portable record ID |
| Source | `id`, `kind`, `uri`, `digest` | `s-` + SHA-256 of canonical citation JSON |
| Entity | `id`, `kind`, `name` | `e-` + SHA-256 of the explicit backticked identifier |

Each structural edge has exactly `source`, `relation`, `target`. Supported edges are
Memory → `SUPPORTED_BY` → Source and Memory → `MENTIONS` → Entity. Two selected
memories citing the same source version or mentioning the same code identifier
share the corresponding node. The graph is regenerated from selected records;
it does not require an existing FalkorDB projection to be fresh or available.

Import validates **the entire explicit topology** against those records before
writing anything. Duplicate nodes/edges, dangling references, unknown fields,
invented links and inconsistent citations are rejected even if the sender
recomputes the checksum. This makes topology reproducible from stored records
without adding a second graph authority to the catalog. After destination-side
review and `sync-graph`, FalkorDB reconstructs the same portable paths alongside
its local team/member/brain structure.

### Optional reviewed-assertion extension

To export assertions, select their exact accepted IDs with repeatable
`--link LINK_UID` in addition to selecting both current endpoint records.
The optional `relations` array contains one to 200 objects with exactly
`source`, `relation`, `target`, `sources`. Endpoints are distinct selected portable
record IDs; supported types are `UPDATES`, `EXTENDS`, `RELATES_TO`. Citation lists
must contain unique canonical-sorted citations belonging to the selected
endpoints. The array is sorted by canonical object JSON and rejects duplicates.

Each corresponding graph edge has exactly `source`, `relation`, `target`,
`assertion` and `evidence`; `assertion` is `l-` plus the SHA-256 of canonical
relationship JSON and `evidence` is its citation list. The explicit graph must
match both structural extraction and the entire assertion list. Arbitrary
relationships, approval fields and extra nodes are still forbidden.

The importer pins assertions to the imported endpoint hashes and stores them as
separate proposals in the same transaction as records and the collection digest.
Accepting records does not accept assertions. After independent assertion review,
re-export preserves the same portable representation. See
[relationship lifecycle](memory-relationships.md) for source validity and privacy.
Older strict version-2 readers reject this extension; omission of `relations`
preserves the base version-2 wire representation.

The digest is SHA-256 of canonical JSON over every envelope field **except
`digest`**. `parent_digest` refers to this digest, rather than a hash of the raw
file bytes. These are integrity/conflict controls, **not cryptographic origin
signatures**. To update an existing collection, set `parent_digest` to the last
successful digest, set each changed record's `expected_hash` to its current
destination content hash, regenerate topology as needed and reseal the envelope.
`brain.abhi_graph.topology` and `seal` implement those canonical operations.
The importer applies the existing transactional compare-and-swap rules; one
bad record rolls back the complete batch. Replaying the same envelope is
idempotent. Missing records do not imply deletion.

Selection is a map of exact current UID → content hash. Export rejects proposed,
rejected, deleted, expired or changed records. It never expands an entity's
neighbors to include unselected memories. The file does not contain membership,
author identities, acceptance state, embeddings, private brain identifiers,
approval, local database paths or unrelated graph nodes. The selected text and
its citation URIs can themselves contain sensitive information and are shown
for independent review in the operator export command.

Destination tenant and team are explicit. Import requires the configured tenant
to match and a current writer/reviewer grant for the destination team. It creates
proposals authored by the configured importing principal; it cannot create a
membership, assume a source author's identity or approve a code constraint.
Review is independent of export/import. Readers cannot retrieve pending proposals
from other members. Exporting accepted team records requires current read access.

Limits: 1 MB UTF-8, 200 selected records, 200 selected assertions, 500 nodes and 1,000 edges, plus the
existing citation/text limits. Export files are newly created with mode 0600
where supported; an existing path or final symlink is never overwritten.

Example operator workflow (absolute paths are placeholders):

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml export-abhi /ABSOLUTE/PATH/selected.abhi --brain private:alice --record RECORD_UID=RECORD_HASH --team backend --collection selected-notes
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml import-abhi /ABSOLUTE/PATH/selected.abhi
# Independently review the imported team proposals, then refresh the projection.
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain team:backend
```

This version deliberately covers **current memory/citation/identifier topology**.
It does not export arbitrary semantic relationships, revision history,
`UPDATES` Version nodes, identities, ACLs, code/decision graph nodes or approval
history. Only the three explicitly reviewed assertion types above are portable.
Tests compare byte-equivalent canonical exports after review/re-export and
normalized live FalkorDB paths after destination import.

Local validation on October 17, 2026: **212 tests passed** in the complete
disposable FalkorDB/Lite suite, including the live `.abhi/2` round trip. The owner
stopped with SAVE; no approved demo graph was used. The existing third-party
Authlib deprecation warning remains. This is component and integration evidence,
not a measured coding-agent improvement or a general privacy/security audit.

## Version 1: team proposals

`.abhi` is UTF-8 JSON, at most 1 MB, with duplicate keys rejected. It is a portable
team proposal interchange format, not an executable file or authority token.
Every envelope and record has exactly the fields shown below; unknown fields
(including membership, principal, state, approval or executable hooks) are rejected.

```json
{
  "format": "abhi/1",
  "tenant": "example",
  "team": "backend",
  "collection": "design-notes",
  "parent_digest": "",
  "records": [
    {
      "id": "upload-rule",
      "text": "Proposed note supported by an explicitly reviewed source.",
      "sources": [{"uri": "https://example.org/reviewed-source", "digest": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}],
      "expected_hash": "",
      "expires": ""
    }
  ]
}
```

Tenant/team/collection identifiers use 1–64 ASCII alphanumeric, `_` or `-`;
record IDs use 1–128 ASCII alphanumeric, `_`, `.`, `:`, or `-` characters and form
bounded `abhi:<collection>:<id>` keys. Metadata types are strict: null/boolean
expiry or expected-hash values are rejected atomically. There are at most 512
records and 1–20 credential-free HTTPS/URN citations per record, each with a
lowercase SHA-256 digest. Text is 1–12,000 characters. Expiry is empty or a future
timezone-aware ISO-8601 timestamp, normalized to UTC.

The configured identity must match the envelope tenant and hold writer/reviewer
membership in `team:<team>`. The file cannot create a team membership. First
import uses empty parent/expected hashes. The result returns the envelope digest;
an update supplies that digest as `parent_digest` and each changed record's
current content hash as `expected_hash`. All changes commit in one transaction.
Duplicate IDs, changed parents, concurrent edits or a failed record abort the
entire import. Reimporting an identical envelope is idempotent.

Content fingerprints are SHA-256 of canonical JSON over text, citations and UTC
expiry. Envelope fingerprints are SHA-256 over sorted-key, compact, UTF-8 JSON
with `ensure_ascii=false`. These are integrity/conflict controls, not signatures.
Missing records are not deletions. Deletion is an explicit reviewer/admin action;
a future format may add signed tombstone exchange after a separate review.
New or changed records remain proposals until independent review. Nothing here
creates graph decisions, approved constraints or executable instructions.
