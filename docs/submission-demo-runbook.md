# Submission recording: signed-token crash

Target a four-minute edited recording. Keep the real run's receipts and label
cuts/time compression. This is a public-repository demonstration with synthetic
company documents, not an observed upstream incident or a performance comparison.

## Prepare before recording

- Reuse the indexed `pallets/itsdangerous` checkout and the uploaded document
  corpus. Confirm the revision and each extraction receipt; retry failed
  sections before recording. A successful retry does not erase earlier failures.
- Use a fresh conversation for the discovery run. Do not carry forward the
  earlier guided question or its answer. Keep the original run labeled guided.
- Complete human review of the personal and team notes below, then enable the
  company evidence connection and refresh their graph projections. Show their
  actual accepted state, author and source. A document named “team decision” in
  Company Brain is not evidence of Team Brain retrieval.
- Confirm the configured test runtime has the repository's existing test
  dependencies. Do not hide setup failures behind an empty passing test suite.
- Use a desktop viewport with readable text. Prefer a focused symbol graph and
  the textual evidence links over a full-graph overview. Check the exported
  recording at normal playback size, including captions and test output.

## Discovery prompt

> Our signed-token validation occasionally crashes with an unexpected Python
> exception. Investigate the root cause using our company knowledge and fix it.

Do not add document names, symbols, filenames or test instructions to this
question. The app separates investigation, planning and approved execution;
show those transitions. If the agent cannot discover relevant evidence, retain
that result and improve retrieval before presenting a successful discovery demo.

## Three-brain preparation

These are proposed demo seeds for a new discovery run, not historical lessons
that the prior recording already retrieved. Have the operator inspect and review
them before sharing. Never label a proposed record “reviewed.”

Personal note:

> Demo operator preference: for signed-token validation changes, require a
> deterministic reproduction that fails against original code, and inspect the
> final diff and matched targeted tests before considering the fix verified.

Team lesson (share only the selected reviewed note into the demo team, then
review the team proposal independently):

> Demo engineering lesson from source inspection: TimestampSigner.unsign in
> src/itsdangerous/timed.py must distinguish signature validity from timestamp
> representability. Review conversion-error normalization while preserving UTC,
> expiration behavior and tampered-token rejection. Source: the synthetic
> engineering decision and the indexed implementation; no upstream policy claim.

For an explicit lexical graph link, the reviewed runtime note also includes
`Code identity: src/itsdangerous/timed.py::TimestampSigner.unsign` (with the
identifier enclosed in backticks). This identifies the file and method already
named in the note. The operator authorized the notes, team copy and code links
in this chat; the acceptance reasons retain that basis.

For a three-brain claim, inspect the new run's tool trace and citations. Require
company code/document evidence, an accepted personal record and an accepted team
record in the same investigation or plan. Open each citation. Show a native
memory-to-company-symbol path only if it is actually returned by the graph; naming
`TimestampSigner` in prose is not proof of a graph link. If this does not happen,
describe the result as Company Brain plus whichever memories it actually used.

## Shot list and narration

| Edited time | Show | Narration / caption |
| --- | --- | --- |
| 00:00–00:15 | Indexed repository, document receipts, revision | “Company Brain connects code and company evidence. This repository and these synthetic documents were loaded before recording.” |
| 00:15–00:25 | Brief ingestion receipt and focused relationships | “Uploads retain their sources and extract advisory relationships. The full ingestion wait is omitted.” |
| 00:25–00:45 | Fresh chat and the exact discovery prompt | “The request names the symptom. The agent chooses the documents, code and tests.” |
| 00:45–01:30 | Active investigation stage; document/code citations and focused symbol | “The agent follows source-backed evidence to explain the crash. A valid signature does not guarantee a representable timestamp.” Use this diagnosis caption only if supported by the new run. |
| 01:30–01:55 | Personal and Team Brain citations, accepted states and actual paths | “These reviewed demo memories contribute a validation preference and an engineering lesson.” Only say this if the run actually retrieved and used both. |
| 01:55–02:20 | Plan, allowed files, exact tests, operator approval | “The operator reviews a bounded plan before the agent can edit an isolated checkout.” |
| 02:20–02:45 | Actual editing/testing stages | “The agent generates the implementation and regression tests. We compare the original and patched code using the same command.” Label any time compression. |
| 02:45–03:20 | Original failure output, named reproduction and matched patched output | Read the actual failure/pass counts. Identify the previously failing reproduction. Do not equate process exit alone with a verified fix. |
| 03:20–03:50 | Final implementation/test diff and downloaded patch | “Here is the generated patch and its regression coverage.” Show exception handling and the relevant test, at readable size. |
| 03:50–04:00 | Report and limitations | “The patch is isolated. These results establish this reproduction and targeted coverage; they do not establish a general coding-performance advantage.” |

Adjust captions to the actual outcome. Do not narrate a successful fix if tests
fail, time out, fail collection or report zero cases. Do not replace recorded
output with authored success cards.

## Evidence to retain

Keep the prompt, run/action IDs, revision, actual model/tool trace, checked
citations, accepted memory review events, exact approved test command, baseline
and patched outputs, final patch and source-checkout cleanliness check. Preserve
any independent replay separately from the agent's own test result.

Before submission, verify the exported video's audio or caption track, readable
test results and final diff, and that it continues past approval through the
outcome. If the original footage is silent, add the narration above or captions
aligned to the final edit. This runbook is not a finished recording.
