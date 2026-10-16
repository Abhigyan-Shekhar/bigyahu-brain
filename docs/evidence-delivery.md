# Historical evidence delivery

`get_context` now returns bounded Source excerpts without requiring a Decision.
The five tool names and input signatures are unchanged. No call-resolution or database
architecture changes were made.

Supported lookups are exact node/Source UIDs, exact issue/PR URLs, `#number` within the
configured repository, and keyword search. Retrieval follows existing `SUPPORTS`,
`SUPPORTED_BY`, and `DISCUSSED_IN → SUPPORTS` links. Existing PR `CHANGES → File`
associations are returned separately. No missing links are created.

Every excerpt lives only in `untrusted_source_excerpts`, with source UID/URL, repository,
graph scope, snapshot time, revision and its meaning, work-item identity/status,
status provenance, retrieval route, confidence, truncation and trust metadata.
`trust_status=untrusted_evidence` and `binding=false` apply even to merged PRs.
Missing metadata is null or explicitly unknown; old snapshots can be reingested to
populate the new status fields. A snapshot revision identifies the indexed checkout,
**not** the historical PR head or merge commit.

Ingestion derives `open`, `closed`, `merged`, `open_proposal`, or `closed_unmerged`
only from structured GitHub snapshot fields, never body text or review prose.
Closed PRs without explicit merge metadata remain unknown. Status is verified as of
the snapshot timestamp, not asserted to be current indefinitely. `work_status` on a
comment describes its parent work item, not approval of that comment.

Evidence paths distinguish direct recorded evidence, file-level historical associations,
heuristic relationships and other recorded relationships. A PR touching a file does not
establish a constraint on every symbol it declares. Coverage reports missing file links. Cross-module retrieval consumes recorded static
import edges, including explicit re-export edges when supplied by the ingester; unrecorded
runtime dispatch remains outside coverage. Confidence labels
describe the recorded relationship, not the truth of arbitrary source claims.

Bounds per response:

- 10 lookup items; 50 paths of at most two hops.
- 20 Source excerpts, at most 2,000 characters each and 12,000 total text characters.
- 20 file associations.
- 1,000 query characters and five search terms.

Limits are reported in the response; truncation categories are explicit. Exact Source
lookups can retrieve an individual source omitted by a multi-item limit. There is no
offset/pagination support; source bodies longer than 2,000 characters remain truncated.
All traversal nodes are constrained to the configured repository and requested graph.
Public retrieval never falls back into a private graph. Private access is restricted to
the configured principal's graph.

## Measured validation

2026-10-15, existing FalkorDBLite engine (FalkorDB module 4.18.3), Python 3.12:

- **48 passed, zero failed/skipped**, 11.41 seconds; two existing Authlib deprecation warnings.
- Ruff and `git diff --check` pass.
- Seven new integration cases include public urllib3 #5181/#5161/#3780/#5242 snapshots,
  exact IDs, URLs, numbers, keywords, source bounds, malicious prose, cross-repository
  edges, private/public isolation and a separate STDIO MCP process.
- **Four real Codex app-server `mcpServer/tool/call` invocations** returned actual database
  excerpts. The client used temporary urllib3 configuration; global Codex registration
  was unchanged. This is protocol verification, not a model-driven coding run.
- #5181 returns source text and reports its absent `CHANGES` edge. #5161 and #3780 carry
  snapshot-verified merged status. #5242 carries `open_proposal`, `binding=false`.
- No real decision was created or approved. Existing synthetic approval tests remain
  confined to unique test repositories.

The first targeted test invocation used a relative `PYTHONPATH`; its STDIO child could
not import the package from a temporary directory. Repeating with the absolute source
path fixed the test invocation. No production launch/configuration changes were needed.

Artifacts: `data/validation/evidence-delivery/tests.txt`, `tests.xml`,
`codex-results.json`, and `verify_codex.py`. Historical screening and negative-control
artifacts remain unchanged; new results do not overwrite the recorded no-go findings.

Reproduce from the project root with the local database running:

```sh
BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 PYTHONPATH="$PWD/src" \
  .venv/bin/python -m pytest -q
```

The Codex probe requires the indexed urllib3 checkout and ingested public snapshots.
Regression tests use checked-in copies under `tests/fixtures/urllib3-history`, isolated
test repository IDs and cleanup. No online GitHub request is required for these tests.

Raw validation/protocol captures are now ignored local records, not checked-in publication inputs. See `security-remediation.md` for the exposure correction and the reviewed `docs/demo/` export.

## Ingestion compatibility follow-up

The service now exposes optional historical-link provenance added by ingestion `c2d9d9a`.
CHANGES associations retain file-level, non-binding semantics. References remain untrusted
mentions, with primary mention-source metadata separate from the referenced issue's source.
Older graphs may return null for new properties. See
[graph-intelligence-progress.md](graph-intelligence-progress.md#compatibility-review-of-ingestion-c2d9d9a--16-october-2026)
for the isolated compatibility review and current validation results.
