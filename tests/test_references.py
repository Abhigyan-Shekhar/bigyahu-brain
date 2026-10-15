import pytest

from brain.ingest.references import issue_mentions


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Fixes #5181 and relates to #3779.", {5181, 3779}),
        ("Refs urllib3/urllib3#5181, URLLIB3/Urllib3#3779", {5181, 3779}),
        ("https://github.com/urllib3/urllib3/issues/5181#issuecomment-123", {5181}),
        ("other/repo#5181 https://github.com/other/repo/issues/3779", set()),
        ("#0 #12345678901 #notanumber https://evil.example/#12", set()),
    ],
)
def test_explicit_issue_mentions(text, expected):
    assert issue_mentions(text, "https://github.com/urllib3/urllib3") == expected
