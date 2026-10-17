# Signed-token coding-action result

On 18 October 2026 (IST), the human operator authorized completion of the
previously guided `itsdangerous` plan. The real application agent generated the
two-file [patch](signed-token.patch) in an isolated checkout. The app then ran:

```text
python -m pytest -q -p no:cacheprovider tests/test_itsdangerous/test_timed.py
```

| Check | Original | Patched |
| --- | --- | --- |
| Original code with proposed regression tests / patched targeted suite | 14 failed, 112 passed | 126 passed |
| Separate reproduction checks in fresh clones | 4/16 passed | 16/16 passed |

The [receipt](verification.json) records the revision, model, action identifier,
test summaries, patch hashes and individual independent check results. These
tests ran through the Codex OS sandbox with network access disabled. The indexed
source checkout remains clean; the patch has not been applied there or pushed.

The fix converts an authentic timestamp once before age checks, catches only
`ValueError`, `OSError` and `OverflowError` from conversion, and reuses the aware
UTC datetime for expiration metadata and timestamp returns. Unrepresentable
timestamps now raise `BadTimeSignature("Malformed timestamp")`, including plain
`unsign`. This behavior change was explicit in the approved demo requirements.

## Replay

Use a fresh checkout of the revision in the receipt and the existing test
runtime. Apply `signed-token.patch` with `git apply`. Run the targeted command
above with that checkout's `src` on `PYTHONPATH`. Copy [reproduce.py](reproduce.py)
into the checkout and execute it with the same source import path for the
separate 16-case check. Run it against the unmodified revision as well: the
original exits 1 with 12 failed assertions or raw conversion exceptions; the
patch exits 0. The independent script was authored after patch generation and
was not supplied to the coding agent.

## Patch export correction

Independent replay caught an application export bug after the coding action:
the generic Git helper stripped the final newline, and `git apply` rejected the
download. The app now preserves raw diff output. The saved report and bundled
patch were re-exported from the already approved isolated checkout; only the
missing final newline changed. The receipt retains hashes of both versions.
The original invalid export remains in ignored local audit storage. Regression
tests now apply exported patches in fresh clones, checking exact file bytes for
both tracked-only changes and patches that add a new test file.

## Demo status

This completes execution of the **guided** investigation. It does not establish
independent document discovery or use of Personal/Team Brain in this action.
The operator subsequently accepted both labeled memory notes, the selected team
copy and company-code links. The [recording runbook](../submission-demo-runbook.md)
defines the fresh discovery prompt, three-brain evidence checks and narration.

## Fresh discovery and three-brain action

A [fresh conversation](discovery.json) used the exact symptom-only prompt. It
made 16 read-tool calls, independently selected the implementation and uploaded
reproduction/acceptance documents, and published four checked claims. Personal
and team evidence was retrieved, but the published answer cited company evidence.
This was not a clean-room benchmark: the human-reviewed synthetic notes were
available and contain implementation hints.

The subsequent [plan](three-brain-plan.json) explicitly requested relevant
personal/team contributions. It cites the personal preference for original-code
failure checks and diff review, the team lesson for preservation coverage, and
company documents/current code for the diagnosis. The team's actual
[MENTIONS → RESOLVES_TO path](reviewed-memory-path.json) resolves the exact
lexical identity to the indexed `TimestampSigner.unsign`. This is a real
source-backed graph path, not proof of causal performance improvement.

The operator separately approved this second plan. The agent generated a
[second patch](three-brain.patch), adding a standalone standard-library unittest
file, and the backend ran the exact approved command against both versions.
The [second receipt](three-brain-verification.json) records:

- Original: 8 test methods, with 5 assertion failures and 18 raw conversion
  errors across subtests. Patched: all 8 methods passed.
- Independent fresh-clone checks: original 4/16; patched 16/16.
- Additional validation using the first run's larger pytest regression corpus:
  126 passed on the second patch. That corpus was not given to the second editor.
- The indexed source checkout remains clean; neither patch has been applied there.

The app's strict automated regression flag remains **false** for the second
action because it rejects baseline runner errors. The recorded errors are the
conversion exceptions under test; independent reproduction verifies these cases
separately. The acceptance rule was not weakened, and no coding lesson is
proposed from that action. Keep this distinction visible when showing its report.

## Review video

The [captioned walkthrough](walkthrough.mp4) is a **100-second edited still-frame
walkthrough**, assembled from actual captured
application states. It is not continuous screen recording. It shows the fresh
prompt, company evidence, personal/team contributions, actual editing stage,
second action's before/after result and generated implementation diff. Waits are
omitted. Its default selectable English subtitle track and [captions.srt](captions.srt) sidecar
provide concise narration, including the synthetic-seed and automatic-gate
disclosures. Enable captions in the player if they are hidden.

[The capture manifest](capture-manifest.json) preserves screenshot hashes, scene timings
and caption text. The complete encoded video decodes without error; its duration
and default subtitle track were checked. Review this local video before deciding
whether to submit it or record the continuous live sequence in the runbook.
The reviewed video and captions are included here; raw screenshots and execution
traces stay in ignored local audit storage. No hackathon submission was performed.

Application validation: frontend production build, Ruff checks, and 36 targeted
backend tests passed, including disposable live FalkorDB document/graph checks
and patch replay regressions. Browser inspection verified persisted extraction
status while citations are open, readable evidence links, and the real completed
patch/test report. This is targeted validation, not a full browser regression suite.
