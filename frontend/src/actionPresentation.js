// Presentation only: does not change the backend verification gate.
export function testSummary(result) {
  const output = result.output || "";
  const unittest = result.argv?.[2] === "unittest";
  const lastCount = (pattern) => {
    const matches = [...output.matchAll(pattern)];
    return matches.length ? Number(matches.at(-1)[1]) : null;
  };
  if (!unittest)
    return {
      count: result.tests_reported ?? null,
      unit: "reported passing tests",
      failures: lastCount(/(\d+) failed/g),
      errors: lastCount(/(\d+) errors?/g),
    };
  const failures =
    lastCount(/failures=(\d+)/g) ??
    (/^OK\s*$/m.test(output) || /FAILED \(/.test(output) ? 0 : null);
  const errors =
    lastCount(/errors=(\d+)/g) ??
    (/^OK\s*$/m.test(output) || /FAILED \(/.test(output) ? 0 : null);
  const headers = [...output.matchAll(/^FAIL: .+$/gm)].map((m) => m[0]);
  const subtests = headers.filter((line) => /\) \(.+\)$/.test(line)).length;
  return {
    count: lastCount(/Ran (\d+) tests?/g) ?? result.tests_reported ?? null,
    unit: "unittest methods/cases",
    failures,
    errors,
    subtests,
    detailsComplete: failures !== null && headers.length === failures,
  };
}

export function elapsedLabel(seconds) {
  if (!Number.isFinite(seconds)) return "Elapsed time unavailable";
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}m ${value % 60}s elapsed`;
}
