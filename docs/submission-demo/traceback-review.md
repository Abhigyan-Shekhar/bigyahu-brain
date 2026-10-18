# Traceback inspection and complete-suite follow-up

This follow-up tests the exact **three-brain.patch** artifact against its pinned
original revision, `672971d66a2ef9f85151e53283113f33d642dabd`. It does not alter
the historical action, its eight tests, approval, or conservative verification
flag. The indexed checkout remains clean. See the machine-readable
[follow-up receipt](followup-verification.json).

## Why the original run had 18 errors

The original untruncated log was inspected, including every `ERROR:` section.
All 18 came from executing tests; none was an import, collection or setup error.
The [complete sanitized log](original-baseline-tracebacks.txt) exposes the stack
traces; [the case-by-case analysis](baseline-error-analysis.json) retains all 18
subtest identities, exceptions, source frames and the original log's digest.
Machine paths are replaced with placeholders; the raw original stays in local
audit storage.

| Count | Cases | Precise cause in original `timed.py` |
| --- | --- | --- |
| 6 | Three injected exception types × `return_timestamp=True` or `max_age=60`, all with valid signatures | `timestamp_to_datetime` was mocked to raise `ValueError`, `OSError` or `OverflowError`. Each escapes at line 156 (timestamp return) or line 145 (expired-token metadata). Two errors per exception type. |
| 8 | `TimedSerializer` and `URLSafeTimedSerializer` × max-age absent/present × timestamp return false/true | Both serializers call `signer.unsign(..., return_timestamp=True)` at line 204. `datetime.fromtimestamp(10**12, timezone.utc)` at line 43 raises `ValueError: year 33658 is out of range`, reached through line 156 or future-token metadata at line 152. |
| 3 | Direct extreme-timestamp `unsign`, with timestamp return, max-age, or both | The same real `ValueError` escapes at line 156 or 152. |
| 1 | Extreme-timestamp `validate(max_age=60)` | `validate` calls `unsign` at line 164; conversion fails at line 152 → 43. `validate` catches `BadSignature`, which does not catch `ValueError`. |

These are **12 real datetime range exceptions and six deliberately injected
conversion exceptions**. The original tests used `assertRaises(BadTimeSignature)`.
Unittest treats a different escaping exception type as an error, rather than an
assertion failure. Five additional assertion failures were separate: three
injected conversions with default `unsign` options did not run at all; extreme
plain `unsign` accepted the token; extreme plain `validate` returned true.

## Minimal regression with a clean assertion outcome

[test_timestamp_regression.py](test_timestamp_regression.py) signs an authentic
token while mocking only the signing timestamp to `10**12`. It restores the
clock before validation, then asserts that timestamp-returning `unsign` raises
exactly `BadTimeSignature`, with the malformed-timestamp message, payload,
absent datetime and conversion-error cause.

It captures the actual exception and compares its exact type. A raw `ValueError`
therefore produces a diagnostic assertion failure; it cannot pass the test.
This changes the new test's reporting, not the historical log or exception
expectation. No application exception is suppressed or normalized by the test.

The identical test file and command ran in fresh original/patched clones under
the same Python **3.12.13**, pytest **8.4.2** and freezegun **1.5.5** installation,
with the same sandbox policy, disabled network and disabled pytest plugin
autoload. Only source/workspace paths differ.

```text
python -m unittest test_timestamp_regression.py -v
```

- Original: **1 assertion failure, 0 errors**; actual exception was `ValueError`.
- Patched: **1 passed**; actual exception was `BadTimeSignature`.
- Feeding these matched outcomes into the existing regression verifier produces
  `tests_passed=true` and `regression_demonstrated=true`. This is a separate
  follow-up result; the historical action's flag is unchanged.

## Conversion logic and invalid-signature compatibility

The current three-brain patch moves the existing guarded conversion out of the
bad-signature branch and reuses its datetime. AST inspection finds **one**
`timestamp_to_datetime` call site in patched `unsign`, compared with **four** in
the original. Instrumented normal, timestamp-returning, max-age boundary,
expired, future and tampered paths each call conversion **exactly once** on the
patch. Undecodable or missing timestamps still skip conversion.

[test_signature_compatibility.py](test_signature_compatibility.py) passed all
**six test methods on both versions**, checking:

- Tampered tokens preserve the cryptographic error message, payload and aware
  UTC `date_signed`; `validate` still returns false.
- Tampered extreme timestamps retain malformed-timestamp normalization.
- Tampered malformed timestamps preserve the signature error with no datetime.
- A bad signature without a timestamp remains exactly `BadSignature`.
- Injected conversion errors retain their cause identity and normalized metadata.
- Unrelated `RuntimeError` exceptions propagate on both signature paths.

The earlier **signed-token.patch** artifact retains separate valid/invalid
signature guards. The current **three-brain.patch**, checked here, consolidates
them; neither artifact converts the same request twice. The current patch needs
no additional conversion refactor.

## Complete itsdangerous test suite

After the minimal regression and compatibility checks, each fresh clone ran:

```text
python -m pytest -q -p no:cacheprovider tests
```

| Selection | Result |
| --- | --- |
| Original complete upstream suite | **297 passed**, no failures or errors |
| Patched complete suite, including the patch's eight new unittest methods | **305 passed**, no failures or errors |
| Patched complete suite plus the minimal regression and six compatibility checks | **312 passed**, no failures or errors |

The last run explicitly includes the two follow-up test files. This checks the
complete itsdangerous suite, rather than only `test_timed.py`. The receipt keeps
commands, exit statuses and output for both versions. No dependencies were
installed and no source fix was needed after the checks.

For manual replay, copy the two follow-up test files and
[inspect_timestamp_conversion.py](inspect_timestamp_conversion.py) into a fresh
checkout, point `PYTHONPATH` at that checkout's `src`, run the commands above,
and execute `python inspect_timestamp_conversion.py`. Apply `three-brain.patch`
in the patched clone only. Use the same interpreter for both clones.
