# .abhi version 1

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
