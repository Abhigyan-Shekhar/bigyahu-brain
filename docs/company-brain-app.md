# Company Brain application

A local React/FastAPI application now connects public GitHub onboarding, real
FalkorDB graph exploration, document upload, conversational Codex investigation,
source inspection, and approval-controlled isolated coding actions. The flow is
**paste repository URL → index → ask → inspect source → plan → approve → patch/test report**.
See [approved coding actions](company-brain-actions.md) for execution requirements
and a reproducible synthetic acceptance check.

## Run

Use Python 3.12, Node.js 20.19+ or 22.12+, Git, an authenticated GitHub CLI and an
installed/authenticated Codex CLI. Use a dedicated operator-owned FalkorDB instance;
the app creates a fresh tenant namespace per connected repository. Existing demo
and memory graphs are not reused. Do not start a second owner on an existing Lite
database.

```sh
uv sync --frozen --extra app --extra lite --extra graphify --extra ingestion --python 3.12
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
- Investigation and planning have read-only tools. After explicit approval, a
  separate editor can read/write only approved paths in an isolated clone through
  digest-checked MCP calls. The backend runs the exact approved Python test
  commands through the Codex OS sandbox. No agent has approval, shell, ingestion,
  credential or publication tools. Plugins/apps/web search are disabled.
  Repository prose is untrusted evidence.
- Citation checks establish source provenance and literal support quotations.
  They do **not** mathematically verify that a model's interpretation follows from
  the quote. The interface distinguishes these and exposes source text for review.
- Supported onboarding: public GitHub repositories under 100 MB metadata size,
  5000 checkout files, 5 MB/file and 50 MB total; no symlinks/submodules. Core
  Python indexing has its own stricter code-size/parser bounds. Full history is
  not promised: Git is shallow at 100 commits; GitHub acquisition is at most 100
  requests and 20 items per collection. Graph views cap at 150 nodes/300 edges.
- Uploads: Markdown/RST up to 500 KB; PDF/DOCX up to 1.4 MB, with bounded text
  extraction and immutable original-file/extraction-snapshot citations. No OCR or
  legacy `.doc`. Select sections in **Document sources & semantic ingestion** to
  run the actual Graphify semantic API or FalkorDB GraphRAG SDK ingestion pipeline.
  Validated advisory relationships enter the same company FalkorDB graph and
  evidence retrieval. Extraction uses the app's selected Codex model; no embedding
  model is required. See [semantic ingestion](semantic-document-ingestion.md).
- [Personal Brain](personal-brain-app.md) supports private notes, exact-consent
  selected-turn proposals and source review with acceptance/rejection/revocation.
  Passing coding actions can propose lessons for review; accepted lessons are
  retrieved and cited through native FalkorDB tools in fresh conversations. Team
  sharing/navigation and `.abhi` controls remain future UI work. The full ten-step
  product acceptance test is consequently **not complete**.

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
uv sync --frozen --extra app --extra lite --extra graphify --extra ingestion --python 3.12
uv run --frozen --extra app --extra lite --extra graphify --extra ingestion python scripts/validate_memory_foundation.py
```

The application tests exercise URL rejection, authentication/Origin/Host checks,
read-only runner configuration, restart recovery, readiness gates, native code and
uploaded-document evidence, invented quotes/IDs, citation access and stale source
rejection. Live suite: **340 passed**. Browser acceptance uses a real public
repository and actual Codex tool calls; see the [milestone report](application-milestone-verification.json).

The [coding action report](application-action-verification.json) records a separate
synthetic fixture run: six agent-written tests fail on the original code and pass
on the patch; a fresh clone with the downloaded patch passes 15 held-out oracle
cases. This does not establish coding effectiveness on production repositories.

The [semantic ingestion report](application-ingestion-verification.json) verifies
real model-backed Graphify and SDK runs, native relationship retrieval, and
PDF/Word original-file and extraction-snapshot citations.

The [Personal Brain report](application-personal-verification.json) verifies the
reviewed lesson → independent native graph recall → checked citation workflow,
plus rejection and revocation on a disposable synthetic fixture.
