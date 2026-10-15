# Graph intelligence progress — 16 October 2026

Implemented on `feat/graph-intelligence`. Initial checkout: `70ec324827344a376f907f9efea356f1a0fccef7`.
The checkout initially contained staged ingestion/security work; it was committed separately as
`0142e748c6f48adfdbc122d4139159a645cb1a52` during inspection. That work and subsequent
concurrent ingestion edits were preserved. This change owns only services, service tests,
and the two graph-intelligence documents. No MCP signature, graph schema, ingestion,
approval CLI, runner, configuration, or recorded experiment artifact was changed by this task.

## Reproduced limitation and smallest fix

With isolated FalkorDBLite, the public #3780 fixture returned nine historical Source excerpts
through `get_context`. `check_change` returned zero, including after recording the existing
File → DECLARES → Symbol relationship. Its evidence query only followed Decisions.

`check_change` now reads the current files declaring targets **and incoming callers**, then
retrieves recorded PR/Issue CHANGES links for those paths, including older File revisions.
It reads bodies through SUPPORTS and discussion through DISCUSSED_IN → SUPPORTS. Where
existing PR → REFERENCES → Issue edges are present, issue bodies and discussion are also
available. It never manufactures an edge or infers an issue/file relationship from prose.

## Changes and query behavior

| Problem | Files | Change | Validation |
| --- | --- | --- | --- |
| History inaccessible without Decisions | `src/brain/services/core.py` | Batched file discovery; bounded CHANGES, SUPPORTS, discussion and optional REFERENCES routes | Live history, caller-file, old-revision, deduplication, poisoning, scope and STDIO regressions |
| CALLS metadata omitted resolution | `src/brain/services/core.py` | Existing incoming 1–2 hop query now returns recorded resolution, target UID, graph revision and deterministic ordering; legacy null resolution falls back to recorded confidence | Synthetic two-hop, legacy-null unit tests, actual urllib3 and Requests STDIO responses |
| Context exact symbol lookup and source flooding | `src/brain/services/core.py`, `src/brain/services/evidence.py` | Exact current qualname lookup alongside existing UID/issue/PR lookup; symbol history uses the same bounded routes; deduplicated items/sources; body routes precede discussion; transparent lookup/retrieval metadata | Existing source lookup/provenance suite and new symbol-context regression |
| Ownership conflated with expertise or stopped after CODEOWNERS | `src/brain/services/core.py` | Keep existing ownership/items fields; separately return Git maintainers and file-associated PR reviewers with source URLs and identity basis; include affected caller files | Real CODEOWNERS/Git/reviewer evidence, identity separation and overflow regressions |
| Silent response truncation and unbounded decision excerpts | `src/brain/services/core.py`, `src/brain/services/evidence.py` | Shared source deduplication and count/text budgets; bound decision source text in queries; repository-filter decision sources; status incomplete when results are truncated | Large/malicious decision text, foreign source, source-count, caller-count and ownership-count cases |
| Old assertions assumed truncated output was complete | `tests/test_core.py`, `tests/test_integration.py`, `tests/test_graph_intelligence.py` | Update existing mocks/status expectations and add six live service/MCP regressions | Complete applicable suite |

All historical and decision prose stays in `untrusted_source_excerpts`, marked
`trust_status=untrusted_evidence`, `binding=false`, repository and scope. Historical sources
retain URL, snapshot time, work status/status basis and revision basis where recorded.
Unknown legacy metadata stays unknown. Source metadata and file associations remain
separate from active decision constraints.

A historical PR-file link is `file_level_historical`; an issue reached through a PR mention
is `file_reference_mention`. Both have `symbol_constraint=false`. CHANGES confidence is
returned as recorded (for snapshots, `snapshot_path_only`). Neither label asserts that a
particular function changed or that the historical prose is correct. A recorded REFERENCES
edge is not verified issue resolution.

The existing binding checks remain: active, human_approved, constraint kind, in-repository
source support, matching approved revision, and a clean matching checkout. Superseded
Decisions do not enter current must_preserve/review. `remember` still creates only proposed
Decisions. No real proposal or approval was created during validation. Synthetic approval,
supersession, private-scope and poisoning regressions continue to pass.

Bounds: 1,000 candidate symbols; 100 caller paths and Decisions; 200 affected files;
20 historical file associations; 50 ownership files; 20 explicit owners and five inferred
maintainers/reviewer records per file. Source delivery shares a 20-item, 2,000-character
per-item, 12,000-character total excerpt budget, including decision prose. Query sentinels
report overflow; large caller/decision sets fail closed. Full-text lookup remains bounded
at four label queries of eleven hits, ten delivered lookup items and fifty graph paths.
Long excerpts or missing result coverage yield explicit truncation/incomplete reporting.
Absent CALLS edges never establish absence of dependencies.

## Validation

Isolated database: `/tmp/brain-graph-intelligence/brain.rdb`, loopback port 6391;
Python 3.12.13, FalkorDBLite 0.10.0, FalkorDB module 4.18.3, Redis 8.6.2.
Original runtime data/configuration were untouched.

Focused service tests passed, followed by live service/MCP tests and the complete suite:
**87 passed**, no skips, 15.36 seconds, two existing Authlib deprecation warnings.
This final run includes the legacy null-resolution adjustment and excludes concurrent
ingestion edits that left the shared checkout. An earlier run with that concurrent work
passed 98 tests. Real STDIO response selections were refreshed against the final branch.

Reproduction with an independently started isolated owner:

```sh
.venv/bin/python scripts/run_lite.py --db /tmp/brain-graph-intelligence/brain.rdb --port 6391
# In another shell, configure BRAIN_TEST_CONFIG to a YAML with repo_root: /tmp,
# repo_id: graph-intelligence-validation, port: 6391.
BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 \
  BRAIN_TEST_CONFIG=/tmp/brain-graph-intelligence-test.yaml PYTHONPATH="$PWD/src" \
  .venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
git diff --check
```

Ruff passes for `src` and `tests`; `git diff --check` passes. Repository-wide `ruff check .`
finds a pre-existing BLE001 in `docs/demo/oracle.py:69`, outside this task's ownership.

Selected actual **separate-process STDIO** responses are in
[`graph-intelligence-examples.json`](graph-intelligence-examples.json), with public source
URLs, revisions, caller confidence and non-binding source status. These are explicitly
shortened response selections, not model-driven coding trials or complete raw captures.

* urllib3 `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`: three requested targets,
  four incoming paths; #3780 and #5161 merged-history bodies, #5242 open-proposal body,
  and #5181 issue body retrieved without Decisions. Its response is incomplete because
  excerpt/evidence/ownership limits are reached. `HTTPConnectionPool.urlopen →
  set_file_position` is static; recursive self-method paths remain heuristic. No false
  PoolManager → HTTPConnectionPool runtime dispatch edge is inferred.
* Requests `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`: target should_strip_auth returns
  rebuild_auth → should_strip_auth and resolve_redirects → rebuild_auth → should_strip_auth,
  both with recorded heuristic method-call confidence. The loaded 21 snapshots have no
  recorded file association for these affected files; check_change reports that gap and
  returns no historical excerpts. `trace_decision(topic="redirect")` returns unknown in
  this isolated graph because it contains no Decisions. Synthetic tests validate tracing,
  approval, source provenance, supersession and stale downgrade independently.

## Remaining limitations and handoff to Person 1

1. Requests issue #4716 is present as historical source evidence, but no recorded graph
   relationship connects it to sessions.py. To make it reachable from check_change,
   ingestion needs a **source-backed Issue/PR → File association**, identifying source UID,
   file path, association confidence, historical/indexed revision meaning and snapshot time.
   A mention alone must stay weaker than a verified fix. The service will not invent it.
2. Function-specific historical relevance needs a separately evidenced work-item → Symbol
   association identifying the actual symbol and historical revision. CHANGES → File cannot
   be upgraded into function-level approval or must_preserve. Existing file routes work now.
3. CALLS covers recorded static lexical/import relationships and heuristic self/cls methods.
   Runtime dispatch, inheritance, ambiguous bindings and external calls can be missing.
   No traversal beyond two incoming hops, embeddings, reranker, or new storage was added.
4. Path-based history can include older or unrelated changes within the same file. Source
   association labels are intentionally weak; exact source/issue/PR lookups provide a
   follow-up route when bounded aggregate responses omit evidence. Pagination is absent.
5. Git author and GitHub identities remain distinct. Reviewer evidence identifies a review
   of a PR touching the file, not a review of each changed function. Missing identity
   metadata is reported as unknown.

The relationship requirements above were sent to “Improve Company Brain graph links”
after explicit user approval. Person 1 replied with ingestion commit `c2d9d9a` and requested
compatibility review; the review is recorded below.

## Compatibility review of ingestion c2d9d9a — 16 October 2026

Reviewed Person 1's committed changes against this branch's services. The ingestion
relationship types/directions, confidence/resolution values, repository-local identities,
and Source properties remain compatible. No blocking compatibility defect was found.

The review found service metadata that needed updating:

- Both coverage responses now describe `recorded_static_imports_including_explicit_reexports`.
  This describes the stored edges the service can consume, not an assertion that an older
  graph contains re-export coverage. Older graphs require re-sync with the newer ingester
  to obtain those edges. Runtime dispatch and unrecorded dependencies remain uncovered.
- CHANGES file associations expose optional `basis`, `snapshot_at`, `association_revision`
  and `revision_basis`, in addition to the existing File revision, confidence and Source UID.
  The association stays `file_level_historical`, with `symbol_constraint=false`.
- Issue evidence reached through a file-associated PR now includes `reference_evidence`:
  the PR UID, primary mention Source UID/URL, confidence, basis, snapshot time and recorded
  resolution_verified value. The issue excerpt's own Source provenance remains separate.
- get_context graph paths expose bounded per-edge `relationship_evidence`. REFERENCES-only
  routes are explicitly `untrusted_reference_mention`; CHANGES/MODIFIES paths retain their
  file-level label. All returned evidence paths have `binding=false`.

These are additive response metadata fields, except the documented coverage-description
string and clearer reference-association label. Public tool signatures and traversal/text
limits remain unchanged. Missing legacy properties return null; no source text is parsed
into new links or approval. No ingestion or approval implementation was edited.

Validation used `/tmp/brain-graph-intelligence-compat`, a temporary local checkout combining
service branch `e5a8bfd`, this follow-up, and ingestion commit `c2d9d9a`, with a dedicated
FalkorDBLite database on loopback port 6392. The delivery branch does not merge Person 1's
commit. Original runtime data and recorded experiments remain untouched.

- Focused service/core/live MCP regressions: **37 passed**.
- Complete service branch with its existing ingestion baseline: **88 passed**, no skips,
  15.15 seconds; both integration flags enabled.
- Complete temporary combined checkout: **114 passed**, no skips, 15.17 seconds; both
  integration flags enabled, including ingestion recovery/idempotency, approval, privacy,
  poisoning, source provenance, separate STDIO and Lite restart tests.
- New service regression validates additive CHANGES/REFERENCES provenance without granting
  authority. Older graph routes and legacy null fields remain covered by the baseline suite.
- Ruff `src/tests` and `git diff --check` pass in both checkouts. Two existing dependency
  deprecation warnings remain; the previously recorded repository-wide demo lint issue
  remains outside this task's changes.
- Actual combined urllib3/Requests syncs and separate STDIO calls preserve the earlier
  flagship results: four urllib3 caller paths and history from #3780/#5161/#5242/#5181;
  two Requests authorization caller paths. Requests #4716 still has no recorded file link.
- An additional actual sync plus separate STDIO probe of a synthetic explicit re-export
  chain (`pkg.__init__ → bridge → util`) returns both incoming paths, upload → target and
  entry → upload → target, all `static` / `statically_resolved_import`. Five tools remain
  discoverable; no constraint was created or inferred.

Selected actual responses from this compatibility check, including the synthetic re-export
probe, are in [`graph-intelligence-compat-examples.json`](graph-intelligence-compat-examples.json).
The original response selections remain as the pre-integration baseline. This report records
Person 2's compatibility acknowledgment for Person 1's integration gate. Requests #4716 and
function-specific historical evidence remain the ingestion limitations listed above.
