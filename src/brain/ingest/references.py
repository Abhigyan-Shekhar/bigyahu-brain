"""Extract explicit issue mentions, not resolution claims, from untrusted text."""

import re
from urllib.parse import urlsplit


def issue_mentions(text, repo_url):
    slug = urlsplit(repo_url).path.strip("/")
    if len(slug.split("/")) != 2:
        return set()
    result = {int(n) for n in re.findall(r"(?<![\w/#])#([1-9][0-9]{0,9})\b", text)}
    for repo, number in re.findall(r"(?<![\w/])([\w.-]+/[\w.-]+)#([1-9][0-9]{0,9})\b", text):
        if repo.casefold() == slug.casefold():
            result.add(int(number))
    for repo, number in re.findall(
        r"https://github\.com/([\w.-]+/[\w.-]+)/issues/([1-9][0-9]{0,9})(?![0-9])(?:\b|/)", text
    ):
        if repo.casefold() == slug.casefold():
            result.add(int(number))
    return result
