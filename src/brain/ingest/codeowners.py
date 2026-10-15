"""GitHub location/last-match precedence, including ownerless clearing rules."""

from pathlib import Path

from pathspec.patterns.gitwildmatch import GitWildMatchPattern


def read_rules(root):
    for location in (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"):
        p = Path(root) / location
        if p.is_file() and not p.is_symlink():
            return location, parse_rules(p.read_text())
    return None, []


def parse_rules(text):
    rules = []
    for number, line in enumerate(text.splitlines(), 1):
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        pattern, *owners = parts
        # GitHub does not support negation, character ranges, or escaped whitespace.
        if pattern.startswith("!") or any(c in pattern for c in "[]\\"):
            continue
        if any(not (owner.startswith("@") or "@" in owner) for owner in owners):
            continue
        rules.append((GitWildMatchPattern(pattern), owners, pattern, number))
    return rules


def owners_for(path, rules):
    result = None
    for matcher, owners, pattern, line in rules:
        if matcher.match_file(path):
            result = {"owners": owners, "pattern": pattern, "line": line}
    return result
