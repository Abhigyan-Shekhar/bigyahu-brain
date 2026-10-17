# Personal Brain and reviewed lessons

The local application now closes the coding lesson loop: a passing coding action
can propose a private lesson, the operator can inspect its pinned report and
accept it, and a fresh conversation can retrieve and cite that accepted memory
through native FalkorDB search. No embedding model is required.

## Use the interface

1. Open **Personal Brain** for the selected repository. Add an explicit note, or
   open **Extract from selected conversation turns**.
2. Select completed user turns and preview the exact text. Confirm that exact
   preview to create proposals. Optional semantic extraction uses the configured
   Codex model; deterministic extraction remains available. Assistant answers
   are excluded from the imported transcript.
3. Select a proposal, inspect its original source, enter a review reason and
   accept or reject it. Only acceptance makes a memory eligible for chat.
4. For coding lessons, finish an approved coding action with passing, positive
   test counts. In its report, choose **Send to Personal Brain review**, then
   **Open Personal Brain**. The source includes the objective, base revision,
   patch digest, changed files, test command and reported results.
5. Start a **New conversation** and ask about relevant reviewed lessons. Open a
   citation to inspect the accepted memory and its native source relationship.
6. Use **Revoke acceptance** to remove a lesson from agent retrieval. Existing
   citations recheck acceptance when opened and become unavailable after revocation.

Submitting a lesson again is idempotent and does not reset an existing review.
The coding report retains its original draft; review state belongs to the memory.
Passing reported tests do not prove that a proposed lesson is universally correct.

## Authorities and boundaries

SQLite remains the authority for private records, permissions, exact-consent
imports and review events. The existing memory projection publishes graph views
to FalkorDB. App chat exposes read-only `memory_search` and `memory_graph`, fixed
to the managed repository tenant and local operator. Search explicitly uses the
`falkor` backend and never falls back to SQLite vectors. Proposed/rejected records
remain visible in the operator's review screen but are excluded from agent tools.

Acceptance validates immutable source snapshots. Search and citation publication
recheck sources, accepted state, version hashes and native graph evidence. Missing,
stale or unavailable graph/source evidence fails closed. Catalog review remains
usable when graph publication is unavailable; the UI reports the failure and
provides **Refresh private graph**. Review requests bind the exact record hash and
state, preventing a stale browser action from accepting a different revision.

Notes use content-addressed snapshots. Conversation memories point to exact
consented user spans. Coding lessons pin the completed action report. These are
local evidence snapshots, not signed third-party attestations. Accepted memories
remain untrusted advisory evidence; they cannot grant permissions, approve an
execution or replace explicit user instructions and current code checks.

Each managed repository currently has a separate private catalog. This screen
does not yet federate personal brains across repositories, manage team membership,
share memories or expose `.abhi` exchange. Semantic correction/link proposals can
be inspected here, but their separate relationship review remains a backend
workflow. There is no hosted multi-user identity or automatic transcript scraping.

## Executed verification

The full isolated live graph suite passed **340 tests**. New coverage checks exact
consent, fixed identity/tenant boundaries, proposal exclusion, hash-bound review,
source tampering, stale projections, revocation, positive test requirements and
idempotent lesson submission.

A real browser workflow used the existing disposable retry fixture: propose the
lesson from its passing six-test coding report, accept it, start a fresh chat and
ask about reviewed retry lessons. The model independently called `memory_search`
and returned **two checked claims** citing the accepted lesson. The citation
inspector displayed native `CONTAINS`, `AUTHORED`, `HAS_BRAIN` and `SUPPORTED_BY`
relationships. Browser checks also rejected an unsuitable note and revoked/restored
the lesson; read-only verification observed empty native search and rejection of
the prior citation during revocation.

[Sanitized verification report](application-personal-verification.json) records
these outcomes. Raw conversations, source snapshots, traces and browser screenshots
remain under ignored local validation storage. Recheck an existing run with:

```sh
PYTHONPATH=src python scripts/verify_app_personal.py \
  --config /absolute/path/base.local.yaml --data /absolute/path/app \
  --project PROJECT --action ACTION --turn FRESH_CHAT_TURN \
  --revocation /absolute/path/revocation-check.json \
  --output /absolute/path/report.json
```

The revocation file records the separate observation made while acceptance was
revoked; the verifier checks current accepted state, audit lifecycle, graph search,
source citations, actual model tool calls and backend source hashes. One synthetic
workflow does not establish general recall quality or a coding advantage.
