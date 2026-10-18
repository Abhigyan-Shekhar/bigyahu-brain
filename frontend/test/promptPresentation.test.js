import test from "node:test";
import assert from "node:assert/strict";
import { promptState, shouldSubmitPrompt } from "../src/promptPresentation.js";
import { graphQuestion } from "../src/workspaceContext.js";

test("large pasted text is preserved and the actual submitted limit includes context", () => {
  const value = "Long paragraph\n".repeat(600);
  const result = promptState(value, null);
  assert.equal(result.valid, false);
  assert.match(result.error, /full text is preserved/);
  assert.equal(result.length, value.length);
  assert.equal(promptState("x".repeat(8000), null).valid, true);
  assert.equal(
    promptState("x".repeat(8000), { selection: "node" }).valid,
    false,
  );
  assert.equal(promptState("😀".repeat(8000), null).valid, true);
  assert.equal(Array.from(graphQuestion("😀".repeat(8000), null)).length, 8000);
  assert.equal(promptState(" \n ", null).valid, false);
});

test("multiline editing and input-method composition cannot accidentally send", () => {
  const enter = { key: "Enter" };
  assert.equal(shouldSubmitPrompt(enter, "one line"), true);
  assert.equal(shouldSubmitPrompt(enter, "pasted\ntext"), false);
  assert.equal(shouldSubmitPrompt({ ...enter, shiftKey: true }, "one"), false);
  assert.equal(
    shouldSubmitPrompt({ ...enter, ctrlKey: true }, "pasted\ntext"),
    true,
  );
  assert.equal(
    shouldSubmitPrompt({ ...enter, metaKey: true }, "pasted\ntext"),
    true,
  );
  assert.equal(
    shouldSubmitPrompt({ ...enter, isComposing: true }, "one"),
    false,
  );
  assert.equal(
    shouldSubmitPrompt({ ...enter, nativeEvent: { isComposing: true } }, "one"),
    false,
  );
  assert.equal(shouldSubmitPrompt({ ...enter, keyCode: 229 }, "one"), false);
});
