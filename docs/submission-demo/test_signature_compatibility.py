"""Compatibility checks that must pass on both original and patched sources."""

import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from itsdangerous import BadSignature, BadTimeSignature, Signer, TimestampSigner

NOW = 1_700_000_000


def tamper(token):
    payload, signature = token.rsplit(b".", 1)
    first = b"A" if signature[:1] != b"A" else b"B"
    return payload + b"." + first + signature[1:]


class SignatureCompatibility(unittest.TestCase):
    def setUp(self):
        self.signer = TimestampSigner("regression-secret")

    def sign_at(self, timestamp):
        with patch.object(TimestampSigner, "get_timestamp", return_value=timestamp):
            return self.signer.sign(b"payload")

    def test_tampered_normal_token_keeps_message_payload_and_utc_date(self):
        token = tamper(self.sign_at(NOW))
        with self.assertRaises(BadSignature) as cryptographic:
            Signer("regression-secret").unsign(token)
        for kwargs in ({}, {"max_age": 60}, {"return_timestamp": True}):
            with self.subTest(kwargs=kwargs):
                with (
                    patch.object(
                        self.signer,
                        "timestamp_to_datetime",
                        wraps=self.signer.timestamp_to_datetime,
                    ) as convert,
                    self.assertRaises(BadTimeSignature) as caught,
                ):
                    self.signer.unsign(token, **kwargs)
                convert.assert_called_once_with(NOW)
                self.assertIs(type(caught.exception), BadTimeSignature)
                self.assertEqual(str(caught.exception), str(cryptographic.exception))
                self.assertEqual(caught.exception.payload, b"payload")
                self.assertEqual(caught.exception.date_signed, datetime.fromtimestamp(NOW, UTC))
                self.assertIs(caught.exception.date_signed.tzinfo, UTC)
                self.assertFalse(
                    self.signer.validate(token, **({"max_age": 60} if "max_age" in kwargs else {}))
                )

    def test_tampered_extreme_token_is_already_normalized(self):
        token = tamper(self.sign_at(10**12))
        with (
            patch.object(
                self.signer, "timestamp_to_datetime", wraps=self.signer.timestamp_to_datetime
            ) as convert,
            self.assertRaises(BadTimeSignature) as caught,
        ):
            self.signer.unsign(token, return_timestamp=True)
        convert.assert_called_once_with(10**12)
        self.assertIs(type(caught.exception), BadTimeSignature)
        self.assertEqual(str(caught.exception), "Malformed timestamp")
        self.assertEqual(caught.exception.payload, b"payload")
        self.assertIsNone(caught.exception.date_signed)
        self.assertIsInstance(caught.exception.__cause__, (ValueError, OSError, OverflowError))

    def test_tampered_malformed_timestamp_keeps_signature_error(self):
        token = tamper(Signer("regression-secret").sign(b"payload.a"))
        with self.assertRaises(BadSignature) as cryptographic:
            Signer("regression-secret").unsign(token)
        with (
            patch.object(self.signer, "timestamp_to_datetime") as convert,
            self.assertRaises(BadTimeSignature) as caught,
        ):
            self.signer.unsign(token)
        convert.assert_not_called()
        self.assertEqual(str(caught.exception), str(cryptographic.exception))
        self.assertEqual(caught.exception.payload, b"payload")
        self.assertIsNone(caught.exception.date_signed)

    def test_invalid_signature_without_timestamp_retains_bad_signature(self):
        token = tamper(Signer("regression-secret").sign(b"payload"))
        with (
            patch.object(self.signer, "timestamp_to_datetime") as convert,
            self.assertRaises(BadSignature) as caught,
        ):
            self.signer.unsign(token)
        convert.assert_not_called()
        self.assertIs(type(caught.exception), BadSignature)
        self.assertEqual(caught.exception.payload, b"payload")

    def test_invalid_signature_conversion_errors_keep_cause_identity(self):
        token = tamper(self.sign_at(NOW))
        for cls in (ValueError, OSError, OverflowError):
            with self.subTest(error=cls.__name__):
                cause = cls("injected conversion error")
                with (
                    patch.object(
                        self.signer, "timestamp_to_datetime", side_effect=cause
                    ) as convert,
                    self.assertRaises(BadTimeSignature) as caught,
                ):
                    self.signer.unsign(token)
                convert.assert_called_once_with(NOW)
                self.assertIs(caught.exception.__cause__, cause)
                self.assertEqual(str(caught.exception), "Malformed timestamp")
                self.assertEqual(caught.exception.payload, b"payload")
                self.assertIsNone(caught.exception.date_signed)

    def test_unrelated_conversion_exception_is_not_swallowed(self):
        for token in (self.sign_at(NOW), tamper(self.sign_at(NOW))):
            with self.subTest(tampered=token != self.sign_at(NOW)):
                cause = RuntimeError("unrelated")
                with (
                    patch.object(self.signer, "timestamp_to_datetime", side_effect=cause),
                    self.assertRaises(RuntimeError) as caught,
                ):
                    self.signer.unsign(token, return_timestamp=True)
                self.assertIs(caught.exception, cause)


if __name__ == "__main__":
    unittest.main()
