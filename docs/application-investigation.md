# Historical investigation and connected memory

The application now retrieves historical candidates with an explicit ranking,
returns reachable Git patch evidence, and exposes reviewed memory-to-company paths
through its read-only agent tools. These remain bounded investigation aids.

## Historical bugs

`search_history(query, files, symbols)` accepts failure text and optional current
file/symbol hints. Across at most 1000 indexed work/source candidates, it ranks
rare-term overlap plus explicit changed-file associations, rather than simply
returning the latest substring matches. Exact current symbol identities map hints
to their declaring files. Results include matched terms/files, current symbols in
those files, related indexed work, checked commit/issue/PR text and up to two
checked Git patch excerpts per candidate. Ten candidates are returned; exceeding
the corpus bound fails closed rather than ranking an undisclosed partial sample.

This is lexical similarity, not a trained semantic bug classifier. A changed-file
association does not establish that every current function in that file changed.
Patch evidence comes from an indexed, reachable commit and is rechecked against
Git when cited. Excerpts stop at 12000 characters and report truncation. Merge
commits or unavailable shallow history can lack patch evidence. A patch explains
what changed; proving why a fix works still needs code reasoning and regression
checks. No repository tests run during read-only investigation.

New repository connections require successful bounded GitHub issue/PR acquisition
by default. The connect dialog offers an explicit code/Git-only fallback by
clearing that requirement. Interrupted graph mutations still fail the job. Tool
results report indexed counts and missing GitHub coverage. Successful acquisition
is not a promise of complete historical GitHub coverage.

## Native memory paths

In Personal Brain, **Connect company evidence** explicitly grants the managed
local operator company-read permission and refreshes private and reviewer-owned
team projections with the existing `CompanyBridge`. Agent tools cannot grant
permissions. Existing team readers do not gain company access from this control.

`memory_search` and `memory_graph` request company evidence only under the current
company grant. Current catalog permissions, source versions, accepted states and
projection readiness still govern every read. Missing or stale projections fail
closed. Disconnecting company evidence removes those paths from subsequent reads
and invalidates prior citations to their graph content.

An eligible path can include reviewed Memory → MENTIONS → explicit code Entity →
RESOLVES_TO → CompanySymbol, plus a native CompanyFile → DECLARES → CompanySymbol.
Private and team source proxies can have a native SAME_CITATION edge when their
URI and digest match. This is a provenance association, not acceptance transfer or
proof of common authorship. Company-source matches require unique checked bytes;
unresolved references remain visible warnings. Arbitrary semantic entity-to-code
resolution is not claimed.

Memory prose and graph metadata have separate evidence handles. **Native memory
path** evidence renders a canonical selected native graph as citable text, with
at most three hops and no neighboring Memory records. This allows the model to
quote actual relationship names and company UIDs without pretending those strings
occur in the original memory prose. Every click rechecks the catalog and graph.
The full graph tool issues at most eight selected path handles per call.

## Citation relevance

After source/quotation/graph checks, a separate tool-free call to the configured
Codex model assesses each claim against its cited evidence. Unsupported or
uncertain claims are withheld with an evidence-gap explanation. Malformed or
unavailable review fails the turn; provenance is rechecked after review. The
interface distinguishes this model review from deterministic source checks.
This consumes an additional model call and may reject useful claims. It is a
fallible relevance and causal-support assessment, not a proof of reasoning
correctness, an independent human review or a benchmark of general bug diagnosis.
Existing saved turns and coding plans retain their recorded validation contracts.

## Repository graph investigation

Double-click a node or select **Node to expand → Expand neighbors**. The authorized
repository endpoint returns 50 current neighbors at a time, with **More neighbors**
for the next page. It includes native callers, declarations, historical changes
and source links where those edges exist. Other repository IDs and missing/stale
nodes are rejected. The accumulated browser view stops at 300 nodes/600 edges;
filtering starts a fresh investigation. Each page retains the 300-edge query cap
and explicit truncation. This is paged neighborhood exploration, not an unbounded
enterprise graph browser or a guarantee that every edge fits one page.

## Explicit repository transfers

Personal Brain → **Transfer selected memories from another repository** lists
accepted private memories from another ready local managed repository. Select up
to ten, inspect the exact preview including its original source snapshots, and
confirm that preview digest. Import rechecks acceptance, version, source bytes and
expiry before creating independent proposals in the destination private catalog.
A separate destination review is required before retrieval. Exact replay preserves
existing review; expiry is preserved. Modified preview/source or revoked original
acceptance blocks a new import. Copied snapshots are bounded to 100 KB.

These are independent point-in-time copies. Later source revocation does not
revoke a previously accepted destination copy. The operator can revoke it there.
This does not merge tenants, move private data automatically, preserve arbitrary
graph topology or relax `.abhi/2` tenant/team checks. Shared organization identity,
a personal brain following users automatically and cross-workspace federation
remain future work.

## Executed verification — October 17, 2026

The full isolated live suite passed **369 tests**, zero failed/skipped. New
coverage checks history ranking and patch revalidation; required GitHub acquisition
versus explicit fallback; the actual application MCP memory tools and company
permissions; citable native paths and disconnection; neighbor paging and scope;
transfer API authentication, exact consent, replay, independent review and source
corruption; and withholding unsupported claims or failing unavailable review.
Ruff, changed Python formatting and the production React build pass.

A real `gpt-6.1-sol` investigation of an authored synthetic retry regression used
11 tool calls (one invalid-argument call recovered on retry), historical patches,
current code, policy and accepted private/team native memory paths. It published
four claims after provenance and relevance review. One procedural claim was
withheld as uncertain because the reviewer had source evidence rather than the
action trace. All eight published citation references reopened through the live
API. All 59 recorded backend implementation hashes match the run. Independent
checks passed three cases on the historical fixed function; the current regressed
function failed the cap and negative-input checks while preserving the zero case.
These authored-fixture checks are not a newly approved application coding run.

A separate real-model adversarial relevance check rejected unrelated cache prose
used for a retry-overflow diagnosis and rejected a root-cause assertion backed only
by a fix message/file association. It accepted two supported code/diff claims.
These four cases do not establish a general precision/recall benchmark.

An earlier real-agent attempt failed closed when graph metadata was quoted as
memory prose; the dedicated native-path evidence fixes that citation mismatch.
The [sanitized report](application-investigation-verification.json) records the
completed run and limitations. Raw fixtures, traces, snapshots and local state
remain ignored. Browser acceptance was initially blocked by a Work browser-access
setting/runtime mismatch. After the desktop app restarted, scoped computer-use
acceptance passed as recorded below. A new public GitHub history demonstration
remains unverified. Previous public-ingestion and coding reports retain their
own scope.

### Browser acceptance follow-up

The actual Codex built-in browser now opens the app and its historical Git patch
and native team-memory path citations. A `delay_ms` filter returned one symbol;
expansion showed its file and policy (3 nodes/2 relationships), then the file’s
historical commits (7 nodes/6 relationships). The onboarding dialog’s required
GitHub history checkbox is selected by default.

Using only authored synthetic fixtures, browser controls selected an accepted
private note in one repository, previewed its exact source/version, copied it as
a destination proposal, inspected its source and separately accepted it with a
review reason. A fresh browser-submitted Codex conversation made two successful
`memory_search` calls and published three provenance-checked, model-reviewed
claims. Its transferred-memory citation opened successfully and displayed the
accepted advisory source with its native evidence path. The accepted copy remains
in the destination synthetic fixture for inspection.

No company grants were changed during this browser pass. Permission/revocation
boundaries and multi-page neighbor results retain their backend regression
coverage; the browser fixture exercised an already-connected company projection
and two ordinary expansion steps. No production source or test suite was edited.
