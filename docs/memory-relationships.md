# Source-backed memory relationships

The memory catalog now stores independently reviewed `UPDATES`, `EXTENDS` and
`RELATES_TO` assertions between exact versions of two records in one brain.
FalkorDB projects these as native directed edges. This supplies a relationship
lifecycle for semantic extractors; it does not itself implement an LLM extractor.

`UPDATES` points from a newer assertion to the assertion it updates. `EXTENDS`
points from an elaboration to the assertion it extends. `RELATES_TO` records a
source-backed association. A human must assess whether the selected relationship
is justified. Relationship acceptance does not erase or suppress either memory,
approve a code constraint, prove chronological order or prevent inconsistent
human assertions. Search still returns the independently eligible records.

## Propose and review

Every proposal pins source UID/hash, target UID/hash, relationship type and one
to twenty citations drawn from the selected endpoint records. Its `L-...` UID
hashes this immutable content. Different cited evidence can create distinct
assertions between the same versions; native edges retain separate assertion UIDs.
Repeating the same proposal is idempotent and retains its current review state.

Proposing requires write access. Proposed endpoint records must be visible to
the proposer; no request may name a different private brain or cross-brain
endpoint. Pending links are visible only to their author and owner/reviewers,
with explicit `include_proposals`. Rejected links are hidden. Team readers see
accepted links only, even when both endpoint memories are already accepted.

Acceptance requires owner/reviewer access and **both exact endpoint versions to
be accepted and unexpired**. It is a separate operation from accepting records.
Reviews compare the expected current assertion state (`proposed`, `accepted` or
`rejected`) and record the reviewer/reason in the event log. Rollback changes the
link back to proposed; rejection hides it. A changed/deleted/rejected/expired or
unaccepted endpoint removes accepted relationship eligibility immediately.
Deleting an endpoint erases its incident catalog links and their audit details.

The existing graph freshness fence covers assertions and review states. Changes
invalidate the manifest until operator `sync-graph`. Each graph read filters
native assertion UIDs before querying edges, so hidden pending links between
otherwise visible memories do not cause a topology mismatch in a fresh reader
view. As with all catalog changes, a new pending link can require projection
refresh; this design does not claim to hide aggregate refresh timing.
The default five tools and optional eight-tool graph server are unchanged;
proposal/review/ingestion remain outside MCP.

## Operator commands

The `--sources` file contains a JSON list of exact endpoint citation objects,
each with `uri` and `digest`. The CLI displays the immutable link and current
endpoint text/citations before the separate interactive review confirmation.

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml propose-link --brain private:alice --source NEW_UID --source-hash NEW_HASH --relation UPDATES --target OLD_UID --target-hash OLD_HASH --sources /ABSOLUTE/PATH/citations.json
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml review-link --brain private:alice --uid LINK_UID --expected-state proposed --action accept --reason 'Checked the correction against both original statements'
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain private:alice
```

Native edges expose `assertion_uid`, `state`, `evidence_json` (canonical citation
JSON) and `basis=source_cited_memory_assertion`. Structural edges use empty
assertion/state fields and `evidence_json="[]"`. A structural record → prior
Version `UPDATES` edge is distinguished by `basis=explicit_record_revision`.
All results are untrusted evidence and `binding=false`.

## Automatic candidate generation

`suggest-links --brain BRAIN --record UID=HASH --record UID=HASH` examines only
two to fifty explicitly selected accepted records. It proposes `RELATES_TO`
when they share an explicit backticked code identifier and cites endpoint
evidence. It never expands to unselected neighbors or infers `UPDATES`/`EXTENDS`.
Candidates use deterministic UID ordering, not chronological inference.
More than 200 suggestions aborts the entire operation. Repeated runs preserve
existing proposal/review states. Each returned item reports its actual state.

This is an association heuristic, not a claim of semantic understanding. Free
text fact/entity extraction, contradictory-statement resolution and automatic
cross-session semantic updates still require an evaluated extraction pipeline.

## Portable assertions

The `.abhi/2` exporter includes no assertions unless their IDs are selected with
repeatable `--link LINK_UID`. Every selected assertion and both selected endpoint
records must be current, accepted and authorized. Files with assertions add a
strict optional `relations` array. It contains only portable endpoint IDs,
relationship type and citations, without actor, review or permission claims.

Import stores links as **new destination proposals**, in the same transaction
as the memory records and collection digest. Record review does not accept them.
After independent relationship review, re-export preserves the portable graph.
Older strict `.abhi/2` readers reject files with this extension; plain version-2
and version-1 imports remain supported. Full historical graph export and origin
signatures remain unimplemented.

## Storage and verification

Schema version 2 adds `memory_links` transactionally to version-1 catalogs without
rewriting existing records. Restore accepts both versions. Each brain is bounded
at 2,000 stored assertions; graph-view and portable-file bounds still apply.
Direct database access remains trusted-operator access and bypasses these checks.

Tests cover schema migration and backup, independent review, stale endpoint
versions, hidden drafts, revocation, invalid provenance, rollback, deterministic
suggestions, deletion, atomic import failure and portable assertions. Live tests
exercise native edge states, parallel assertions and `.abhi/2` round trips.

Local verification on October 17, 2026: **228 tests passed** in the full disposable
FalkorDB/Lite suite. The owner stopped with SAVE. Ruff and publication/history
scans passed; the existing third-party Authlib deprecation warning remains.
No actual project records were accepted, no approved demo graph was modified,
and no fresh coding-agent improvement was measured.
