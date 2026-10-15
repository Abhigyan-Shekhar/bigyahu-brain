# Graph backend progress — 16 October 2026

## Scope and baseline

Implemented on `feat/graph-ingestion`, isolated from the shared service checkout.
Baseline: `0142e74` (the existing scoped-identity and issue-reference implementation).
The initial audit found that implementation already in the working tree; it was
committed by another engineer during the audit. It is credited as baseline here.
No MCP, approval, service implementation, experiment runner, or evaluation artifact
was modified by this change. No merge or publication was performed.

Reviewed README, contracts, graph storage, AST/import resolution, sync, Git parser,
CODEOWNERS, snapshots, and unit/live tests against the current checkout.

## Implemented behavior and evidence

- `bindings.py` shares conservative binding analysis between lexical and imported
  call resolution. Conditional definitions/imports, assignments/deletions,
  exception/pattern bindings, variadic arguments, enclosing closure bindings, and
  evaluated definition expressions prevent unjustified edges. Nested function
  imports no longer incorrectly shadow a parent's import.
- Explicit `from` re-exports, including aliases and multi-module chains, resolve
  to the defining function when every module and binding is unambiguous. Cycles,
  wildcard exports, rebound or conditional exports, decorated targets, and
  conflicting module/package layouts remain unresolved. A module file also
  blocks treating its name as a namespace package. Same-module constructors
  retain their existing supported edges.
- Function decorators/defaults/annotations are no longer treated as calls executed
  by the function body. Existing `self`/`cls` dispatch remains **heuristic** and is
  suppressed after receiver rebinding; inheritance/dynamic dispatch is not inferred.
- Existing `PR-[:REFERENCES]->Issue` edges gain exact primary `source_url`,
  `snapshot_at`, `relationship_type`, and `provenance`. Existing `source_uid`,
  bounded `source_uids`, `confidence=explicit_text_reference`,
  `basis=untrusted_source_mention`, and `resolution_verified=false` remain.
  Both body and comment evidence are untrusted mentions. No closing/approval
  semantics are inferred. Refreshing an included PR removes obsolete mention edges.
- `CHANGES` now states `basis=historical_file_association`, indexed revision/basis,
  and snapshot timestamp. `MODIFIES` records the commit Source, historical path
  confidence/basis, commit revision, and indexed revision. A historical path match
  is not proof that a commit changed today's symbol definition.
- Sync reports actual ingested file count, AST call-site count, and statically
  resolved import call-site count. The previous file count included a trailing
  empty `ls-files` element and non-file entries. Other result fields remain.

For example, Requests `tests/test_lowlevel.py:59` calls `requests.get`; its explicit
re-export in `src/requests/__init__.py` connects that call to `src/requests/api.py::get`.
In urllib3, `src/urllib3/util/__init__.py:20` explicitly re-exports the wait helpers;
`WrappedSocket.recv` now connects to `src/urllib3/util/wait.py::wait_for_read`.
CALLS edges retain `confidence`, `resolution`, AST method, line, and caller file UID.

## Same-revision measurements on real FalkorDB

Engine: isolated FalkorDBLite 0.10.0, Redis 8.6.2, graph module 4.18.3 on loopback
port 16389. Dedicated before/after graphs; the experiment database was not touched.
Both revisions were synced twice and snapshot manifests were hash/scope validated.
Git history is the existing bounded most-recent-100-commit window.

| Measurement | urllib3 before | urllib3 after | Requests before | Requests after |
| --- | ---: | ---: | ---: | ---: |
| Unique Symbol nodes | 2,058 | 2,058 | 787 | 787 |
| AST symbol records | 2,093 | 2,093 | 807 | 807 |
| CALLS graph edges | 819 | 745 | 274 | 375 |
| Static import graph edges | 322 | 294 | 145 | 251 |
| Resolved AST call sites | 964 | 869 | 291 | 416 |
| Static import AST call sites | 395 | 353 | 154 | 284 |
| Unresolved function-body calls | 7,928 | 7,579 | 2,338 | 2,094 |
| Issue–PR REFERENCES edges | 1 | 1 | 0 | 0 |
| PR–File CHANGES edges | 11 | 11 | 3 | 3 |

- urllib3 revision: `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`.
- Requests revision: `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`.
- urllib3 uses the four public records in `tests/fixtures/urllib3-history`; Requests
  uses the 21 records in `data/sources`. Missing referenced issues are reported,
  never manufactured. Requests has no issue-target match in this bounded packet.
- Comparing endpoint tuples: urllib3 adds 13 and removes 87 CALLS edges;
  Requests adds 116 and removes 15. Net edge count is not an accuracy score.
- Unresolved counts also change because definition metadata is excluded from
  function-body ownership. Their decrease must not be read as pure resolution gain.
- The existing UID contract collapses repeated definitions, overload stubs and
  property accessors with the same qualified name. Hence AST record totals differ
  from unique Symbol nodes. MERGE also collapses repeated caller/callee call sites
  into one graph edge, retaining a single line; AST counts are separately reported.

## Incorrect/ambiguous relationships discovered

The old resolver could bind `HTTPAdapter.proxy_manager_for` to the conditional
fallback `SOCKSProxyManager` in Requests `adapters.py:66`, despite the alternative
successful external import. That target is now unresolved. Exception and match
bindings, closure parameters and duplicate module layouts have focused regressions.

Conservative exclusions also remove some valid runtime relationships: decorated
`run_hypercorn_in_thread`, overloaded `cookiejar_from_dict`, and context managers
such as `set_environ`. Their wrappers/repeated definitions require more specific
analysis before restoring exact edges. Dynamic monkeypatching, import hooks,
instance types, inheritance, and arbitrary re-exports remain outside this analysis.

## Verified Cypher paths

Use `$repo='github.com/urllib3/urllib3'` on the completed indexed revision:

```cypher
MATCH (a:Symbol {repo_id:$repo, current:true,
                 qualname:'HTTPConnectionPool.urlopen'})-[r:CALLS]->
      (b:Symbol {repo_id:$repo, current:true, qualname:'set_file_position'})
RETURN a.path, b.path, r.line, r.confidence, r.resolution
```

Verified `src/urllib3/connectionpool.py` → `src/urllib3/util/request.py`, line 772,
`static`, `statically_resolved_import`, before and after.

```cypher
MATCH (i:Issue {repo_id:$repo, number:5181})<-[r:REFERENCES]-
      (p:PR {repo_id:$repo})-[c:CHANGES]->
      (f:File {repo_id:$repo, current:true})-[:DECLARES]->
      (s:Symbol {repo_id:$repo, current:true})
RETURN i.number, p.number, f.path, s.qualname, r.basis, c.basis
LIMIT 20
```

Verified issue 5181 → PR 5242 → `src/urllib3/poolmanager.py` → `PoolKey`.
This traverses a mention and historical file association to a declaration; it
**does not** assert that the issue constrains or the PR directly changes `PoolKey`.

```cypher
MATCH (p:Person {repo_id:$repo})-[:AUTHORED]->
      (c:Commit {repo_id:$repo})-[r:MODIFIES]->
      (f:File {repo_id:$repo, current:true})
RETURN p.identity_basis, f.path, r.basis, r.source_uid
LIMIT 1
```

Verified Git author → Commit → `.github/dependabot.yml` for urllib3 and
`.github/workflows/codeql-analysis.yml` for Requests.

## Synchronization and tests

107 tests pass with both documented live opt-in flags; lint and diff checks pass.
Two dependency deprecation warnings remain (Authlib/FastMCP).

```sh
PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q
BRAIN_TEST_CONFIG=/absolute/path/to/isolated-test.yaml \
  BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 \
  PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q
.venv/bin/ruff check src tests
git diff --check
```

The isolated config selects loopback port 16389. The Lite lifecycle test allocates
its own ephemeral port/database. New live tests verify explicit re-export targets,
repeat-sync result/edge stability, exact file count, historical provenance,
injected mutation failure leaving `syncing=true`, recovery to a new completed SHA,
stale revision flags, absence of stale CALLS edges, and refreshed reference removal.
Existing live tests cover cross-file target creation order, repository/private
boundaries, source-backed issue/PR traversal, and shared identity migration.
Parsing/encoding is still completed before mutation; once mutation starts readers
must refuse `syncing=true`. Concurrent sync writers remain unsupported.

## Person 2 interface handoff and merge gate

The pre-existing `0142e74` identity design is retained: Person/Team nodes are
repository-local (`<repo>:identity:<identity>`) with `repo_id`, while `identity_uid`
preserves the common external identity. No shared Person's repo_id is overwritten;
Git and GitHub identities remain distinct. No new identity migration was introduced
in this delta. Existing multi-repository and legacy-author tests pass.

All relationship types, directions, confidence values, and resolution values stay
compatible. Sync result fields and edge provenance properties are additive.
Person 2 should update any coverage description saying `direct_static_imports_only`
to describe explicit re-exports and the exclusions above; the classification
`file_level_historical` must remain for CHANGES paths. Do not treat REFERENCES as
issue closure, binding approval, or symbol constraints.

The user authorized the Person 2 handoff after the initial message was blocked by
automatic approval review. The handoff was delivered, and Person 2 confirmed the
relationship types/directions/confidence values are compatible. Their service
follow-up is exposing additive historical provenance and updating the coverage
description. Final integration waits for that tested follow-up.

A conflict-free trial merge of ingestion `c2d9d9a` with service `e5a8bfd` passed
113 tests with real FalkorDB/Lite flags, including STDIO; lint passed. These are
combined-code checks in a temporary checkout, not a merge of either delivery branch.
The source-URL regression now additionally checks comment-only evidence, repeated
snapshot ingestion, and removal of the final mention. No shared-contract file
was changed.
