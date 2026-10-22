# Native Codex validation: Windows CI fixes

The native skill and MCP integration completed a model-driven investigation,
test edit and test run against this real repository at `397ed0a`. No defect was
seeded. The task was the actual Windows failure in
[workflow 39762855872](https://github.com/Abhigyan-Shekhar/bigyahu-brain/actions/runs/39762855872).

## Findings and changes

The two editor-diff tests used `Path.write_text()` to create fixtures, then sent
digests computed from LF strings. On Windows the fixtures became CRLF bytes.
The editor correctly rejected the mismatched digests, so no diff event existed.
The fixtures now write explicit LF bytes and assert successful tool responses.
A separate regression verifies that real CRLF files require the exact byte
digest, reject LF-normalized digests without a write or event, and preserve CRLF
bytes after a successful edit. Production digest and approval code is unchanged.

The 61,441-character Markdown input was used as its default pytest parameter ID.
Pytest copied that ID into `PYTEST_CURRENT_TEST`, exceeding Windows' environment
value limit. Short descriptive IDs retain all original inputs and assertions.

## Model-driven trial

An isolated local clone, separate FalkorDBLite engine and source-pinned config
were initialized before the run. A fresh `codex exec` invocation used the existing
Company Brain skill, the standalone MCP server and ordinary Codex editing/test
tools with a workspace-write sandbox. Only the three failing test files were
authorized for editing. The agent was not given the diagnosis or a patch.

The recorded trace shows 19 completed MCP calls across repository status,
history, context, impact, ownership, code search, source reads and citation
reopening. Thirteen calls returned checked evidence, including six citation
reopens. All graph retrieval happened before the first edit. Seventeen calls
returned `ok`; an invalid `scope=repo` returned an error and was corrected, and a
keyword context query returned `unknown`. These were visible limitations rather
than invented evidence. The skill now explicitly states the valid scope values.

The model produced the three-file patch, ran the tests and completed normally.
The patch was reviewed before application to the working branch. The sanitized
[receipt](native-codex-trial.json) preserves counts and the baseline revision.
Raw prompts, source excerpts, full command traces and local paths remain in
ignored local validation storage and are not publication artifacts.

## Validation

- On macOS, the three original files passed before the fix: 40 passed, 1 skipped.
- A portable simulation of Windows text-write defaults and environment limits
  reproduced the two failures plus the Markdown setup/teardown errors.
- After the patch, the three files passed: 41 passed, 1 skipped. The model's
  portable reproduction plus the new CRLF regression passed all seven cases.
- Twenty-one targeted byte-replay, digest, scope and approval checks passed.
- An independent full suite against isolated FalkorDBLite passed: 657 passed, 1 skipped.
- The independent Windows-behavior reproduction plus CRLF regression passed all seven cases.
- Ruff, skill frontmatter validation and diff checks passed.

The model trial and portable reproduction ran on macOS. They do not establish
native Windows execution support for the application's approval sandbox. A real
Windows CI run is a separate check; its result is recorded on the validation PR.
Plugin distribution is also separate from this skill-and-MCP validation.
