# Combined v5 and Browser verification — 17 October 2026 (IST)

Integrated `codex/v5-execution` at `f499cbc` with
`parthgenx/browser-demo-verification` at `b68aa5f`, including current master
`0ce80c1`. The merge retains the five v5 commits, native document ingestion,
filtered source snapshots, six-session evaluation and Browser portability work.

The only Git conflict was `.gitattributes`. Resolution retains both trial patch
whitespace rules and LF snapshot/shell rules, and also pins the v5 source snapshot
to LF. Status, submission and video documentation now distinguish the two graphs.

## Fresh combined checks

- Locked Python 3.12 environment: `uv sync --frozen --extra lite --python 3.12`.
- Full suite with `BRAIN_INTEGRATION=1`, `BRAIN_LITE_TESTS=1` and a disposable
  loopback `BRAIN_TEST_CONFIG`: **144 passed, zero failures or skips**. This
  includes real graph, STDIO, privacy, document ingestion and Lite restart tests.
- `ruff check src tests scripts`: passed. Existing FastMCP/Authlib dependency
  deprecation warnings remain.
- Browser preparation and all **11 database query checks** passed against a
  separate empty Lite database: 2,525 nodes; D-1/D-2 remain proposed. Source sets
  and caller lines match. This run did not invoke human approval or test the UI.
- v5 `prepare` passed against another empty Lite database, using the included
  snapshots and clean urllib3 checkout pinned to
  `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`. Its rule remains proposed.
- All validation owners stopped with SAVE. Existing experiment/runtime databases
  were not used. Raw logs, generated configs and new databases remain ignored.
- All six public trial patch hashes match the frozen evaluation manifest.
  Snapshot digest matches; source snapshots, trial patches, evaluation results,
  protocol, lifecycle/document evidence and original demo patch are unchanged.

The first suite attempt used an incomplete validation config with no repository
URL; its document PR-link test failed (143 passed, one failed). Supplying the
fixture repository URL restored exact PR reference matching. No production code
or test assertions were changed to obtain the passing run.

## Evidence boundaries

The [frozen evaluation](v5-evaluation.md) remains a historical result on its
recorded backend and lockfile hashes. Portability edits change current config,
Git/snapshot loading and lockfile bytes; they do not retroactively update those
trial inputs. No coding trial was rerun as part of this integration.

The [Browser receipt](browser-demo/verification-receipt.json) describes a separate
reconstructed graph with a seeded editorial Document/REFERENCES path and policies
on `HTTPConnectionPool.urlopen`. The frozen v5 graph uses ingested document
sections/MENTIONS and policies on `PoolManager.urlopen`. Existing sampled footage
is not footage of the v5 corpus. New combined rebuilds do not inherit historical
approvals, Browser UI acceptance or coding outcomes.

The final narrated video, original v5 visual acceptance, submission-form check,
manual publication/export review and public-access confirmation remain separate
release tasks.
