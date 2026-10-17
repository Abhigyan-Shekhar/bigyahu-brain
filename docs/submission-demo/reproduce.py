"""Independent signed-token checks; run with the selected checkout's src on PYTHONPATH."""

import json
from datetime import UTC
from functools import partial
from unittest.mock import patch

from itsdangerous import BadTimeSignature, TimedSerializer, TimestampSigner, URLSafeTimedSerializer


def check(name, operation):
    try:
        operation()
        return {"case": name, "passed": True}
    except Exception as exc:  # noqa: BLE001 - retain each failed reproduction outcome
        return {"case": name, "passed": False, "error": type(exc).__name__}


def rejects(operation):
    try:
        operation()
    except BadTimeSignature as exc:
        assert type(exc) is BadTimeSignature
        assert str(exc) == "Malformed timestamp"
        assert exc.date_signed is None
        assert isinstance(exc.__cause__, (ValueError, OSError, OverflowError))
    else:
        raise AssertionError("Unrepresentable timestamp accepted")


def main():
    signer = TimestampSigner("demo-secret")
    with patch.object(TimestampSigner, "get_timestamp", return_value=10**12):
        token = signer.sign(b"demo-payload")
    cases = []
    for label, kwargs in [
        ("plain", {}),
        ("timestamp", {"return_timestamp": True}),
        ("max_age", {"max_age": 60}),
    ]:
        cases.append(
            check(
                "signer_extreme_" + label, partial(rejects, partial(signer.unsign, token, **kwargs))
            )
        )

    def invalid():
        assert signer.validate(token) is False

    cases.append(check("validate_extreme_returns_false", invalid))

    for cls in (TimedSerializer, URLSafeTimedSerializer):
        serializer = cls("demo-secret")
        with patch.object(TimestampSigner, "get_timestamp", return_value=10**12):
            serialized = serializer.dumps({"message": "demo-payload"})
        for timestamp in (False, True):
            for kwargs in ({}, {"max_age": 60}):
                cases.append(
                    check(
                        f"{cls.__name__}_extreme_timestamp={timestamp}_age={bool(kwargs)}",
                        partial(
                            rejects,
                            partial(
                                serializer.loads, serialized, return_timestamp=timestamp, **kwargs
                            ),
                        ),
                    )
                )

        def normal_serializer(serializer=serializer):
            payload, dt = serializer.loads(
                serializer.dumps({"ok": True}), max_age=60, return_timestamp=True
            )
            assert payload == {"ok": True} and dt.tzinfo is UTC

        cases.append(check(cls.__name__ + "_normal_utc_roundtrip", normal_serializer))

    def normal_plain():
        assert signer.unsign(signer.sign(b"ok")) == b"ok"

    def normal_timestamp():
        payload, dt = signer.unsign(signer.sign(b"ok"), max_age=60, return_timestamp=True)
        assert payload == b"ok" and dt.tzinfo is UTC

    cases.extend(
        [
            check("signer_normal_roundtrip", normal_plain),
            check("signer_normal_utc", normal_timestamp),
        ]
    )
    passed = sum(c["passed"] for c in cases)
    print(json.dumps({"passed": passed, "total": len(cases), "cases": cases}, indent=2))
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
