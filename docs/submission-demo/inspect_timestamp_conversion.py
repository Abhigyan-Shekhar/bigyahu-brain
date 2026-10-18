"""Report static conversion sites and observed calls for representative paths."""

import ast
import inspect
import json
import textwrap
from unittest.mock import patch

from itsdangerous import BadSignature, TimestampSigner

NOW = 1_700_000_000


def main():
    tree = ast.parse(textwrap.dedent(inspect.getsource(TimestampSigner.unsign)))
    sites = sum(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "timestamp_to_datetime"
        for n in ast.walk(tree)
    )
    results = {}
    for label, age, kwargs, tampered in [
        ("plain", 0, {}, False),
        ("return_timestamp", 0, {"return_timestamp": True}, False),
        ("max_age_boundary", 60, {"max_age": 60}, False),
        ("expired", 61, {"max_age": 60}, False),
        ("future", -1, {"max_age": 60}, False),
        ("tampered", 0, {}, True),
    ]:
        signer = TimestampSigner("regression-secret")
        with patch.object(TimestampSigner, "get_timestamp", return_value=NOW):
            token = signer.sign(b"payload")
        if tampered:
            payload, signature = token.rsplit(b".", 1)
            token = payload + b"." + (b"A" if signature[:1] != b"A" else b"B") + signature[1:]
        outcome = "returned"
        with (
            patch.object(TimestampSigner, "get_timestamp", return_value=NOW + age),
            patch.object(
                signer, "timestamp_to_datetime", wraps=signer.timestamp_to_datetime
            ) as call,
        ):
            try:
                signer.unsign(token, **kwargs)
            except BadSignature as exc:
                outcome = type(exc).__name__
        results[label] = {"conversion_calls": call.call_count, "outcome": outcome}
    print(json.dumps({"conversion_sites_in_unsign": sites, "paths": results}, indent=2))


if __name__ == "__main__":
    main()
