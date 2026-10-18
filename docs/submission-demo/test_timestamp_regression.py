"""One-case contract check, identical on original and patched source imports."""

import unittest
from unittest.mock import patch

from itsdangerous import BadTimeSignature, TimestampSigner


class TimestampRegression(unittest.TestCase):
    def test_signed_out_of_range_timestamp_raises_bad_time_signature(self):
        signer = TimestampSigner("regression-secret")
        with patch.object(TimestampSigner, "get_timestamp", return_value=10**12):
            token = signer.sign(b"payload")

        # Capture the actual exception so unittest reports a mismatched type as
        # an assertion failure, while preserving its type and message in output.
        # An unexpected exception can never satisfy the exact-type assertion.
        with self.assertRaises(Exception) as caught:
            signer.unsign(token, return_timestamp=True)

        self.assertIs(type(caught.exception), BadTimeSignature)
        self.assertEqual(str(caught.exception), "Malformed timestamp")
        self.assertEqual(caught.exception.payload, b"payload")
        self.assertIsNone(caught.exception.date_signed)
        self.assertIsInstance(caught.exception.__cause__, (ValueError, OSError, OverflowError))


if __name__ == "__main__":
    unittest.main()
