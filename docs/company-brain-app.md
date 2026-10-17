# Company Brain application — first milestone

A local React/FastAPI application now connects public GitHub onboarding, real
FalkorDB graph exploration, document upload, conversational Codex investigation,
and source inspection. This is the first milestone from the application brief:
**paste repository URL → index → ask → inspect cited source and native graph path**.

## Run

Use Python 3.12, Node.js 20.19+ or 22.12+, Git, an authenticated GitHub CLI and an
installed/authenticated Codex CLI. Use a dedicated operator-owned FalkorDB instance;
the app creates a fresh tenant namespace per connected repository. Existing demo
and memory graphs are not reused. Do not start a second owner on an existing Lite
database.

```sh
uv sync --frozen --extra app --extra lite --python 3.12
npm ci --prefix frontend
npm run --prefix frontend build
# Terminal 1: own a NEW disposable/persistent application database.
uv run --frozen --extra app --extra lite python scripts/run_lite.py \
  --db data/runtime/company-brain-app/brain.rdb --port 6398
```

Create a local connection config (never commit credentials or machine paths):

```yaml
# config/app.local.yaml
repo_root: /ABSOLUTE/PATH/TO/THIS/REPOSITORY
repo_id: app-connection-template
principal: app_operator
host: 127.0.0.1
port: 6398
```

The base `repo_root` is only needed to validate the connection template. The app
assigns each new source its own managed checkout, repository ID and tenant. The
base memory catalog and embedding settings are not inherited.

```sh
# Terminal 2: explicitly select the model whose account usage chat will consume.
uv run --frozen --extra app --extra lite python -m brain.app.server \
  --config /ABSOLUTE/PATH/config/app.local.yaml \
  --data /ABSOLUTE/PATH/data/runtime/company-brain-app/sources \
  --model gpt-6.1-sol --port 8787
```

Open the printed local session URL, which includes a bearer token in its fragment.
The client removes the fragment and retains the token in this tab's session
storage. Each application restart issues a new token; open the new URL in a fresh
tab (or reload it) after restarting. Build assets before launching the server;
generated assets and Node dependencies are ignored. Development: `npm run dev
--prefix frontend` provides the Vite client, but the production same-origin build
served by FastAPI is the supported authenticated workflow.

## What runs

1. A public HTTPS GitHub URL creates a persisted indexing job. The server checks
   public visibility, clones the default branch with up to 100 commits into a new
   workspace, checks size/file/symlink/submodule limits before checkout, and runs
   the existing Python AST/Git indexer. It never imports the repository's Python,
   installs its dependencies or runs its scripts during onboarding.
2. Bounded existing GitHub sync acquires accessible issue/PR snapshots. Acquisition
   fails before mutation on pagination/request limits. If unavailable, the UI
   reports missing GitHub coverage; code and Git commit history remain available.
   A failed graph mutation/readiness fence fails the onboarding job instead.
3. Existing Markdown/RST ingestion indexes at most 12 repository documents,
   256 KB/file and 1 MB total. Coverage limits are visible. Uploaded UTF-8
   Markdown/RST files are stored separately under an immutable content digest,
   split into bounded sections and linked as native `Document → SUPPORTS → Source`
   evidence. Uploading does not commit to or dirty the repository checkout.
4. A persisted chat session stores questions and published answers. Each turn
   launches an isolated read-only `codex exec` process with up to six prior turns
   as context. Codex chooses the tool order itself. There are no task fixtures,
   required lookup sequences, preselected files or canned answers in this path.
5. Application MCP adapters reuse `get_context`, `check_change`, `find_owner` and
   `trace_decision`, plus bounded `search_code`, `read_code` and `search_history`.
   These three adapters expose indexed file/symbol lookup, original source bytes,
   and recorded commit/issue/PR messages without shell access. Global MCP tool
   signatures and the existing coding demo runner are unchanged.
6. Read tools mint citation IDs into a per-turn evidence ledger. Code evidence
   requires a current native `Project → CONTAINS → File` relationship and a full
   file-byte digest match. Repository documents also match original file lines;
   uploaded sources match the saved content digest and literal section. Historical
   work/commit evidence is explicitly a **recorded snapshot**, not a fetch or claim
   of current GitHub content.
7. The answer schema requires source IDs and exact quotations for each claim. The
   server re-resolves every citation, checks its quotation and graph, and withholds
   the draft on invented IDs, unsupported quotes, changed source or graph evidence.
   Clicking a citation performs these checks again and opens the original text,
   source link and native FalkorDB subgraph. Graph paths are never model-generated.

The Codex runner uses documented [non-interactive JSON and structured output](https://developers.openai.com/codex/noninteractive).
CLI authentication/model access must already work on the operator's machine. The
application does not collect model credentials.

## Boundaries and honest status

- This milestone is for one trusted local operator, bound to `127.0.0.1`, with
  bearer authentication and Host/Origin checks. It is not hosted multi-user auth.
  The UI makes the read-only investigation mode explicit.
- The agent has no shell, editing, test execution, ingestion, credentials, review,
  or approval tools. Plugins/apps/web search are disabled. Repository prose is
  untrusted data; the agent cannot turn it into tool permissions.
- Citation checks establish source provenance and literal support quotations.
  They do **not** mathematically verify that a model's interpretation follows from
  the quote. The interface distinguishes these and exposes source text for review.
- Supported onboarding: public GitHub repositories under 100 MB metadata size,
  5000 checkout files, 5 MB/file and 50 MB total; no symlinks/submodules. Core
  Python indexing has its own stricter code-size/parser bounds. Full history is
  not promised: Git is shallow at 100 commits; GitHub acquisition is at most 100
  requests and 20 items per collection. Graph views cap at 150 nodes/300 edges.
- Uploads: one Markdown/RST file up to 500 KB and 100 sections. No PDF/semantic
  extraction runs. Uploads join the selected company graph through their source
  relationships; automatic cross-brain or document-to-symbol inference is not
  claimed. Repeating identical bytes is idempotent.
- Personal/team brain controls, consented conversation review/sharing, `.abhi`
  controls, approved isolated patch/test execution and the lesson-proposal loop
  are the following milestones. The existing backend retains these capabilities;
  this application does not yet expose them. The full ten-step product acceptance
  test is consequently **not complete**.

Local jobs, sessions, managed repositories, snapshots, uploads, model traces and
per-turn source-hash manifests stay beneath the selected `--data` directory. Keep
it under ignored `data/runtime` or `data/validation`. A restarted queued/running
job is marked failed rather than silently claimed complete. Failed sources can
be reconnected into a new workspace. There is no automatic publication or merge.

## Checks

```sh
uv run --extra app pytest -q tests/test_application.py
npm ci --prefix frontend
npm run --prefix frontend build
# Full disposable live graph suite, including existing memory and Graphify tests:
uv sync --frozen --extra app --extra lite --extra graphify --python 3.12
uv run --frozen --extra app --extra lite --extra graphify python scripts/validate_memory_foundation.py
```

The application tests exercise URL rejection, authentication/Origin/Host checks,
read-only runner configuration, restart recovery, readiness gates, native code and
uploaded-document evidence, invented quotes/IDs, citation access and stale source
rejection. Live suite: **299 passed**. Browser acceptance uses a real public
repository and actual Codex tool calls; see the [milestone report](application-milestone-verification.json).
