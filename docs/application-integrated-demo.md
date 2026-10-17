# Integrated application demonstration

The bounded synthetic application journey now runs through real model/tool calls:
reviewed personal lesson → accepted team copy → browser `.abhi` round trip →
reviewed import + indexed company policy → cited investigation/plan → explicit
approval → isolated patch/tests → independent replay → independently reviewed new
coding lesson → separate fresh-chat recall.

This is a synthetic correctness and integration demonstration from an existing
indexed fixture. Public onboarding and PDF/Word Graphify/SDK ingestion have
[separate executed reports](application-ingestion-verification.json). The run does
not claim a fresh public-repository demonstration of every component, automatic
company graph federation, hosted identity or improved coding performance.

## Reproduce the journey

Start the local app using the [run guide](company-brain-app.md), with its existing
operator-owned FalkorDB connection and explicit Codex model. Keep runtime files
under ignored storage. To add a new disposable namespace without altering any
connected repository:

```sh
PYTHONPATH=src python scripts/prepare_app_action_fixture.py \
  --config /absolute/path/base.local.yaml --data /absolute/path/app \
  --model YOUR_CODEX_MODEL
```

Select **Synthetic coding acceptance fixture**. It contains an intentionally
incorrect `delay_ms` and an indexed `policy.md`; the source URL is explicitly an
example, not a hosted repository. No evaluator code is provided to the agent.

1. In **Personal Brain**, propose a durable note such as: “Validate negative retry
   inputs before calculation; preserve growth, cap-boundary and integer-zero
   regression checks.” Inspect the source and explicitly accept it. This is a
   declared scenario seed, not a claim that the model learned it from a prior fix.
   The recorded run instead reused the real coding lesson reviewed in the earlier
   application milestone.
2. Create a local team, optionally add a disposable reader, and share only the
   selected accepted record. Independently accept its team proposal. Member
   navigation shows shared contributions without opening another private brain.
3. In **Portable memory**, select that record, preview and download a collection.
   Upload the actual file, validate the matching tenant/team and confirm import.
   Inspect the imported proposal and accept it separately. Re-export that imported
   record using the same collection. The complete portable envelope should match.
4. Start a **New conversation** and ask: “How should we fix delay_ms using the
   reviewed imported retry lesson and indexed policy? Cite both, inspect the
   implementation and callers, and explain regression coverage.” Let Codex choose
   its own tools. Inspect both company and imported-memory citations.
5. Choose **Plan a change**. Request a policy-conforming `delay_ms` fix with the
   imported lesson's regression coverage and standard-library unittest tests.
   Planning is read-only. Inspect permitted files, supporting evidence and the
   exact backend-generated test command.
6. On this disposable fixture, approve the reviewed isolated execution. The editor
   works in a separate checkout. Proposed tests run first against original code,
   then against the patch. The indexed checkout remains unchanged.
7. Inspect the report and download the actual patch. Passing tests alone are not
   an independent correctness result. Use the verifier below to replay the patch
   in another clone and check 15 held-out cases through the OS sandbox.
8. **Send to Personal Brain review**, then **Open Personal Brain**. Inspect the
   pinned action report, changed files and positive test counts; enter a reason
   and accept the new lesson independently. The original action report retains
   its frozen draft, separate from catalog review state.
9. Start another **New conversation** and ask about the newly reviewed lesson.
   For a precise replay, reference `lesson:ACTION_ID`, using the action ID in the
   downloaded patch filename. Inspect the citation and native source relationship.
   This last check demonstrates explicit-record recall, not semantic discovery of
   which lesson is most recent.
10. Check the report and preserved audit artifacts. No automatic apply, commit,
    push, merge, grant or memory acceptance occurs through the agent.

## Recorded result

The [sanitized verification](application-exchange-verification.json) records:

- Actual browser export/upload/review/re-export: **one record, two portable nodes,
  one edge**, with the complete envelope unchanged. Native search excluded the
  import before review and retrieved it after acceptance.
- Fresh investigation: **13 actual read-tool calls, three checked claims**, with
  current code, company policy and the reviewed imported memory as support.
- Separate planning: **nine actual read-tool calls, three checked claims** citing
  policy and the reviewed import. The model called `memory_search` and
  `check_change` in both phases; backend hashes match the recorded runs.
- Approved files: `retry.py` and `test_retry.py`; command:
  `python -m unittest test_retry.py -v`.
- **Five agent-written tests** fail against original code and pass after the
  patch. The actual downloaded patch matches the saved report; replay in a fresh
  clone passes **15 held-out oracle cases**, while the original fails. The
  indexed checkout is still clean and consumed approval replay is rejected.
- The new coding lesson was independently accepted and graph-verified. A separate
  one-turn chat, explicitly referencing its memory ID, made a real memory lookup
  and published **two checked claims** citing that new lesson.
- The complete isolated backend/application suite passed **350 tests**.

The agent combined memory and company evidence through separate authorized read
tools. This is not evidence that it traversed one universal native relationship
from the imported lesson to the company policy. Citation checks establish source
provenance, version and literal quotation; they do not prove semantic entailment.
Model output/test counts can differ on another run, and no causal baseline benefit
is established by this one synthetic task.

## Verify an existing run

Preserve the two actual browser downloads as `original.abhi` and `reexported.abhi`,
the downloaded patch as `downloaded.patch`, and the pre-review observation as
`pre-review.json` in ignored audit storage. The pre-review observation records the
imported UID, envelope digest and exclusion from native search while still pending.
Then run:

```sh
PYTHONPATH=src python scripts/verify_app_exchange.py \
  --config /absolute/path/base.local.yaml --data /absolute/path/app \
  --project PROJECT --team TEAM --audit /absolute/path/audit \
  --turn INVESTIGATION_TURN --action CODING_ACTION --recall FINAL_RECALL_TURN \
  --output /absolute/path/report.json
```

The verifier checks current source snapshots, native graph, accepted states,
actual model traces and backend hashes, then independently replays the patch. It
never approves an action, grants membership or accepts a memory. It deliberately
rejects changed backend code or stale/revoked evidence rather than treating an old
report as current proof. Old milestone reports describe their recorded commits;
the new integrated report describes this complete synthetic journey.
