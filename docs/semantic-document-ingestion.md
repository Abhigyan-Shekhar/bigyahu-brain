# Semantic document ingestion

The application accepts PDF and Word (`.docx`) uploads alongside Markdown/RST.
**Add document → select source sections → choose an engine → Extract relationships**
builds advisory entity/relationship evidence in the same native FalkorDB company
graph used by chat and the graph explorer.

## Setup and use

```sh
uv sync --frozen --extra app --extra lite --extra graphify --extra ingestion --python 3.12
npm ci --prefix frontend
npm run --prefix frontend build
```

Launch the app and its dedicated database as described in the
[application guide](company-brain-app.md). The app's explicit `--model` is reused
for semantic extraction. Existing Codex authentication/model access must work.
Selecting **Extract relationships** sends only selected extracted text to that
model and consumes account usage. Uploading alone performs local text extraction
and source indexing, without a model call.

Open **Document sources & semantic ingestion**, select up to eight sections from
uploaded documents or indexed repository Markdown/RST, choose **FalkorDB GraphRAG
SDK** or **Graphify semantic pass**, and start extraction. Job progress and results
persist across page reloads; interrupted jobs fail visibly on server restart.
Chat, uploads and coding approvals wait for active semantic ingestion. Source
changes are also blocked while a coding plan awaits approval.

## Actual integrations

- **Graphify:** pinned `graphifyy==0.9.92`, public
  `graphify.llm.extract_files_direct` semantic API. Its OpenAI-compatible backend
  connects to an ephemeral bearer-protected loopback provider bridge that invokes
  the existing tool-free Codex structured extractor. This runs Graphify's actual
  semantic prompt, parser, sanitization and evidence-binding path. It does not
  require an OpenAI API key or send requests directly to the OpenAI REST API.
  Graphify's separate structural repository CLI remains available unchanged.
  Upstream: [headless extraction](https://github.com/Graphify-Labs/docs/blob/main/guides/headless-extraction.mdx).
- **FalkorDB GraphRAG SDK:** pinned `graphrag-sdk==1.4.0`, actual
  `IngestionPipeline` with provided text, `FixedSizeChunking`, `GraphExtraction`,
  `LLMExtractor` and `ExactMatchResolution`. A custom `LLMInterface` uses the same
  Codex extractor. The SDK builds lexical provenance, extracts/verifies entities
  and relationships, prunes/resolves them, and writes into a staging storage
  adapter. Validated output then enters Company Brain through a native FalkorDB
  storage adapter, preserving its tenant/source contracts. This is a real SDK
  ingestion integration, not the earlier chunker-only comparison.
  Upstream: [ingestion API](https://falkordb.github.io/GraphRAG-SDK/api-reference/),
  [custom providers](https://falkordb.github.io/GraphRAG-SDK/providers/).
- **Graph-only indexing:** the SDK's vector indexing hook is explicitly disabled.
  No embeddings, vector store, SDK retrieval/completion or automatic ontology
  evolution are claimed. Company Brain's existing native graph/full-text
  retrieval reads these relationships and checked source excerpts.

Neither extractor controls Cypher syntax, permissions, coding approval, identity,
or accepted memory. Entities require literal source names; relationships require
valid endpoints and literal evidence spans. Relation names pass an identifier
allowlist and remain properties on fixed `EXTRACTED_RELATION` edges, never dynamic
Cypher. Semantic confidence is `INFERRED` or `AMBIGUOUS`; it never becomes reviewed
policy authority. A literal span does not prove the model's interpretation.

Extraction completes and all output validates before a single atomic graph
publication query. Retry refresh retires prior output for the same input/engine/
model batch. Evidence sources are copied per entity to keep citation paths
unambiguous while preserving original provenance. Local private audit files save
model output, input digests and implementation hashes. Raw files, snapshots, audit
records and runtime paths remain under ignored application storage.

## Binary source provenance and bounds

PDF uses `pypdf`, accepts 1–50 unencrypted text-bearing pages and retains page
markers. A page without extractable text rejects the upload; there is no OCR.
DOCX uses `python-docx`, preserving body paragraph/table order and table rows.
Legacy `.doc`, macros, encrypted packages, images, embedded attachments,
headers/footers and layout fidelity are unsupported.

Original bytes and normalized extracted text are separate content-addressed
artifacts. Citations recheck the original file hash, immutable extraction snapshot
hash, extracted text digest, section text and native graph relationship. Displayed
line numbers refer to **extracted text**, not byte offsets in a PDF/ZIP container.
The evidence API labels this `original_file_digest_and_extraction_snapshot`.

Bounds: binary input 1.4 MB; extracted text 500 KB/100 sections; PDF decoded content
10 MB; DOCX 1000 entries/10 MB expanded size. Parsing runs in a 30-second child
process. Semantic jobs accept eight sections/40000 characters, 200 entities/400
relationships and 1 MB worker output, with a 600-second worker timeout. The source
picker lists at most 201 sections. These are bounded local-operator integrations,
not production parser isolation or enterprise throughput claims.

Repository onboarding continues its bounded Markdown/RST ingestion. Binary files
are uploaded explicitly; an automatic whole-repository semantic scan is not run.
Model selection affects recall and relationship quality. Precompute/review the
hackathon fixture instead of assuming every fresh extraction yields the same graph.

## Verification

[Recorded browser acceptance](application-ingestion-verification.json) uses small,
explicitly synthetic PDF/DOCX policies and real Codex calls through both engines.
It checks native FalkorDB entity/edge counts, source provenance on every entity,
and retrieval of actual `EXTRACTED_RELATION` paths. A real follow-up chat returned
three source-checked claims citing both formats, and the Word citation was opened
in the inspector. It is not an accuracy benchmark.

Reverify existing completed jobs without calling a model or changing the graph:

```sh
PYTHONPATH=src python scripts/verify_app_ingestion.py \
  --config /ABSOLUTE/PATH/config/app.local.yaml \
  --data /ABSOLUTE/PATH/data/runtime/company-brain-app/sources \
  --project PROJECT_ID --output data/validation/ingestion-report.json
# Add --turn TURN_ID to reverify a completed chat citing both formats.
```

The verifier requires both engines' latest completed jobs, their audit artifacts,
current implementation hashes and original/snapshot evidence. Unit/integration
coverage includes invalid/blank PDF, Word table order/expanded-archive bounds,
invalid model endpoints/spans/identifiers, actual SDK pipeline stages with a
controlled provider, idempotent native graph publication, and original-file and
snapshot tamper rejection. The full local suite includes optional ingestion
coverage when installed; default CI skips the optional SDK-provider test when the
SDK extra is absent. No model/network calls run in routine unit tests.
