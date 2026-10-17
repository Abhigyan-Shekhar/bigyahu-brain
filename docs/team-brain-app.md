# Team Brain application

The local application now supports explicit sharing, separate team review,
permission-filtered member navigation and native FalkorDB recall of shared
memories. Open **Team Brain** beside Personal Brain in the sidebar.

## Use the interface

1. **Create a local team** with a repository-scoped identifier. The configured
   operator becomes its creator and reviewer. Existing team names cannot be
   claimed by creating them again.
2. Under **Manage team membership**, enter a catalog principal, role and reason.
   Readers see accepted shared evidence; writers can submit proposals; reviewers
   can review evidence and refresh projections. Only the local creator can manage
   membership in this interface. Their reviewer role cannot be removed here.
3. Under **Share an accepted personal memory**, select one reviewed memory and
   preview the destination, full selected text, author, expiry and citations.
   **Propose selected memory to team** copies that exact revision using the
   existing explicit sharing contract. The surrounding private conversation and
   coding-report envelope are excluded.
4. Select the shared proposal and inspect its source references. A reviewer enters
   a reason and accepts or rejects it. Acceptance is independent of the private
   record's review. Repeated sharing preserves an already accepted identical copy;
   conflicting revisions require explicit reconciliation.
5. Click a member to inspect their shared contributions and permitted native graph
   slice. **All members** restores the team view. This filter does not impersonate
   the member or open their private brain. A member with no contributions has an
   empty memory slice.
6. Start a fresh conversation and ask about the team's reviewed lessons. The agent
   can retrieve accepted private and currently authorized team memories with
   `memory_search` and inspect their native graph with `memory_graph`. Team
   citations recheck live membership, accepted state, source snapshot and topology.

Membership changes bind the previously displayed role. A stale browser submission
cannot overwrite a concurrent change. Review binds the exact record hash and
state. Revoking membership blocks subsequent reads and citation resolution for
that principal; revoking team acceptance removes the shared record from chat.
Private and team copies have independent lifecycles: revoking a private record
does not recall a copy already explicitly shared and reviewed by a team.

## Sources and graph authority

SQLite continues to own identities, grants, review and audit. FalkorDB owns the
rebuildable native memory graph and exact/full-text retrieval. No embedding model
or SQLite vector fallback is used. Sharing retains the selected record's original
citation references and stores an immutable, hash-checked snapshot containing only
selected text, citations, author and record hash. Team readers do not fetch a
private source envelope to validate the shared record.

The app reuses existing `share_memory`, `Memory.review`, `MemoryGraph` and
`MemoryTools` contracts. A writer can save a proposal but cannot refresh a
reviewer-owned graph. The response reports that a reviewer must refresh it;
accepting the proposal refreshes through the reviewer. Graph/source failure is
reported, and stale evidence fails closed. Review and membership remain available
as catalog operations while FalkorDB is unavailable.

App read tools have no identity, team selection, grant, share or review arguments.
The server derives authorized retrieval scopes from current grants, with a maximum
of ten scopes. An untouched private brain is omitted because it has no records or
projection; this lets a new team reader retrieve shared evidence. UI lists cap at
100 teams, 100 members per app-managed team and 100 visible records; graph views
retain the existing bounded projection and 150-node/300-edge display limits.

This remains a trusted loopback operator application. Catalog principals are not
hosted login accounts; creating a member does not connect another person's device.
There is no private-brain federation, automatic company semantic bridge, hosted
identity provider or enterprise-scale claim. [`.abhi` app controls](abhi-app.md) now expose selected export, strict import and
independent assertion review. Existing CLI interchange is also preserved.

## Executed verification

The full disposable live suite passed **345 tests**. Team regressions exercise
reader proposal exclusion, writer submission without reviewer privileges,
review and membership conflicts, tenant isolation, source tampering, revocation,
member slices and a conversation-derived share that excludes surrounding private
text. Earlier test attempts exposed an empty-private-projection search issue and
writer refresh handling; both were fixed before the passing suite.

Browser acceptance on the disposable retry fixture created a team and reader,
shared the prior coding lesson, accepted it and inspected member views. Read-only
checks verified zero reader results before team acceptance, one afterward, and
blocked search/citation access during membership revocation. Membership was then
restored. A fresh one-turn real Codex conversation independently called
`memory_search` and published **one checked claim** citing the accepted team
memory. The browser citation inspector showed its native source and author paths.

The [sanitized verification report](application-team-verification.json) and
`scripts/verify_app_team.py` recheck the actual tool trace, pinned backend hashes,
source snapshot, current reader access, member graph slices and recorded lifecycle.
Raw source text, traces, runtime configuration and screenshots remain ignored.
The pre-review/revocation observations are recorded separately while those states
are active; the verifier reads these artifacts after membership restoration. One
synthetic workflow does not establish general retrieval quality or coding benefit.
