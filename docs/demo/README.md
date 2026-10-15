# Company Brain: recorded graph-assisted coding workflow

**Workflow demonstrated; implementation failed; no measured improvement.**

The demo video replays actual emitted Codex events. It is not a live screen capture. Source excerpts, proposed edits and results are preserved, with local machine details removed. The full raw traces remain in local research artifacts.

- Model: gpt-6-luna, medium reasoning; Codex CLI 0.162.0-alpha.17.2.
- urllib3 revision: a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8.
- FalkorDBLite 0.10.0; Redis 8.6.2; graph module 4.18.3; Python client 1.8.0.
- Company Brain tests: 70 passed. Exact cross-module HTTPConnectionPool.urlopen → set_file_position edge verified with real FalkorDBLite.
- Only four read-only tools exposed; remember disabled; only those read-only calls automatically approved. Shell sandbox retained. Valid scopes: org/private.
- Eligible work history: merged urllib3 #5161 and #3780. Solution PRs #5242 and #5191 excluded, including #5181's solution-revealing comment. No decisions approved.

## Actual workflow

The separately guided model chose get_context twice in org. It retrieved #5161 through PR→Source and discussion paths and saw six file-level associations. Source prose stayed untrusted and non-binding; file associations are snapshot-based history, not symbol constraints. Each response was bounded to 50 paths and disclosed truncation. Eight source records per response include empty review bodies; the second lookup repeats the same sources.

The model explicitly said history reinforced preserving 303 body disposal, then edited PoolManager and added a 307 regression. It did not retrieve #3780 or choose check_change; the newly verified imported-call edge was not part of its selected retrieval. Local code and tests already show much of the relevant behavior. #5161 contains a merged implementation for a related problem, so this is not independent discovery.

The separate guided session is excluded from the paired comparison. It received explicit org-evidence guidance but no previous patch, independent evaluator feedback or implementation hints. It ran a parent-directory AGENTS filename search despite the checkout-only instruction; the search returned no output. No sibling content or evaluator exposure was observed, but perfect read isolation was not enforced.

## Measured result

Demo: 9/12 independent socket cases, 6/6 bare-pool controls, 52 targeted upstream tests passed (741 deselected). The agent's own socket tests were sandbox-blocked. The patch fixes ordinary replay but introduces early UnrewindableBodyError for failed-tell uploads before any bytes are sent, including no redirect and 303. This patch must not ship.

Paired experiment: three attempts per arm, only two baseline and one graph coding sessions completed. The other sessions hit usage limits. The completed graph session queried empty private scope twice and retrieved no history. All six evaluated checkouts scored 9/12, but completed patches and untouched checkouts failed different cases. This is incomplete descriptive evidence and supports no improvement claim.

Docker FalkorDB 4.14.7 remains unverified because no Docker runtime was available. The Lite demonstration was not delayed.

## Public provenance and attribution

- [Task: urllib3 #5181](https://github.com/urllib3/urllib3/issues/5181)
- [Merged history #5161](https://github.com/urllib3/urllib3/pull/5161), author [@SEPURI-SAI-KRISHNA](https://github.com/SEPURI-SAI-KRISHNA), public review [@illia-v](https://github.com/illia-v).
- [Merged history #3780](https://github.com/urllib3/urllib3/pull/3780), author [@chromy](https://github.com/chromy), public discussion [@nateprewitt](https://github.com/nateprewitt).
- [Pinned source](https://github.com/urllib3/urllib3/tree/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8)

Public handles are source-recorded attribution, not ownership or Company Brain decision approval. urllib3 code/patch context remains under its included MIT license. Oracle is retained unchanged from the screening run. Full review snapshots have collection-time provenance, not proof that prose was unchanged at an earlier historical cutoff.

## Reproduce independent behavior

Apply demo.patch in a fresh checkout of the pinned revision, create Python 3.12 with the pinned repository lockfile, and run:

```sh
uv sync --frozen --python 3.12 --group test
PYTHONPATH="$PWD/src" .venv/bin/python /path/to/oracle.py
.venv/bin/python -m pytest -q test/with_dummyserver/test_poolmanager.py test/test_util.py test/with_dummyserver/test_connectionpool.py -k 'redirect or file_position or rewind or file_body or failed_tell'
```

The oracle exits 1 because failures are preserved. Machine paths, environment logs, account identifiers, credentials and private graph data are excluded from this bundle. Nothing was uploaded or published.
