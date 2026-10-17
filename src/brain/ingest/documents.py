"""Bounded, deterministic repository documentation; prose never grants authority."""

import ast
import hashlib
import re
import tokenize
from collections import defaultdict
from itertools import pairwise
from pathlib import PurePosixPath

from .bindings import bindings
from .git_parser import clean, git, revision
from .references import issue_mentions

DEFAULT_PATHS = ("CHANGES.rst", "docs/reference/urllib3.poolmanager.rst", "docs/user-guide.rst")
MAX_FILES, MAX_FILE_BYTES, MAX_TOTAL_BYTES = 12, 256_000, 1_000_000
MAX_SECTIONS, MAX_LINES, MAX_CHARS = 512, 40, 1800
QUALIFIED = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+"
REFERENCES = re.compile(
    rf":(?:py:)?(?:class|meth|func):`~?({QUALIFIED})`"
    rf"|\.\. auto(?:class|method|function)::\s*({QUALIFIED})"
    rf"|``({QUALIFIED})``|(?<!`)`({QUALIFIED})`(?!`)"
)


def symbol_resolver(texts, symbols):
    """Exact qualified names and explicit from-import re-exports, without imports.

    No suffix guessing, inherited members, assignment aliases or dynamic dispatch.
    Ambiguous package names and rebound definitions fail closed.
    """
    paths = defaultdict(list)
    for path in texts:
        parts = list(PurePosixPath(path).with_suffix("").parts)
        if parts[0] == "src":
            parts.pop(0)
        if parts[-1] == "__init__":
            parts.pop()
        paths[".".join(parts)].append(path)
    exports, definitions = {}, {}
    for name, candidates in paths.items():
        if len(candidates) != 1:
            continue
        path = candidates[0]
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        tree = ast.parse(texts[path], filename=path)
        exports[name], _ = bindings(tree.body, package)
        stable = set()

        def definitions_in(body, prefix="", package=package, stable=stable):
            for node in body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    _, writes = bindings([n for n in body if n is not node], package)
                    if node.name in writes or "*" in writes:
                        continue
                    qual = f"{prefix}.{node.name}" if prefix else node.name
                    stable.add(qual)
                    # A nested function is not a qualified attribute of its parent.
                    if isinstance(node, ast.ClassDef):
                        definitions_in(node.body, qual)

        definitions_in(tree.body)
        by_qualname = defaultdict(list)
        for symbol in symbols:
            if symbol["path"] == path and symbol["qualname"] in stable:
                by_qualname[symbol["qualname"]].append(symbol["uid"])
        definitions[name] = {k: v[0] for k, v in by_qualname.items() if len(v) == 1}

    def resolve(reference, seen=()):
        if reference in seen or len(seen) >= 12:
            return None
        pieces = reference.split(".")
        for end in range(len(pieces) - 1, 0, -1):
            module, qual = ".".join(pieces[:end]), ".".join(pieces[end:])
            if len(paths.get(module, [])) != 1:
                continue
            # Every indexed ancestor must be a unique package, not a module collision.
            if any(
                len(paths.get(".".join(pieces[:i]), [])) > 1
                or any(not p.endswith("/__init__.py") for p in paths.get(".".join(pieces[:i]), []))
                for i in range(1, end)
            ):
                return None
            if qual in definitions.get(module, {}):
                return definitions[module][qual]
            first, *rest = pieces[end:]
            binding = exports.get(module, {}).get(first)
            if binding and binding[2] == "from":
                return resolve(".".join([binding[0], *rest]), (*seen, reference))
            return None
        return None

    return resolve


def sections(text):
    """RST/Markdown headings delimit sections; long sections split into bounded ranges."""
    lines = text.splitlines(keepends=True)
    starts = {0, len(lines)}
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+", line):
            starts.add(i)
        if i and re.fullmatch(r"[=~^\-`:#*+]{3,}\s*", line) and lines[i - 1].strip():
            starts.add(i - 1)
    boundaries = sorted(starts)
    for start, stop in pairwise(boundaries):
        while start < stop:
            end = start
            size = 0
            while end < min(stop, start + MAX_LINES):
                if len(lines[end]) > MAX_CHARS:
                    raise ValueError("Document line exceeds section bound")
                if size + len(lines[end]) > MAX_CHARS:
                    break
                size += len(lines[end])
                end += 1
            body = "".join(lines[start:end])
            if body.strip():
                yield start + 1, end, body
            start = end


def ingest_documents(store, paths=None):
    cfg = store.cfg
    sha = revision(cfg.repo_root)
    state = store.revision()
    if not clean(cfg.repo_root) or state != {"sha": sha, "syncing": False}:
        raise ValueError("Document ingestion requires clean checkout at completed indexed revision")
    paths = list(dict.fromkeys(DEFAULT_PATHS if paths is None else paths))
    if not paths or len(paths) > MAX_FILES:
        raise ValueError("Document file count exceeds bounds")
    tracked = set(git(cfg.repo_root, "ls-files", "-z").split("\0"))
    prepared, total = [], 0
    for path in paths:
        cfg.path(path)
        file = cfg.repo_root / path
        if path not in tracked or file.suffix not in {".rst", ".md"}:
            raise ValueError("Expected tracked RST or Markdown file")
        if any(p.is_symlink() for p in (file, *file.parents)) or not file.is_file():
            raise ValueError("Document symlinks and non-files are not allowed")
        if file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Document file size exceeds bounds")
        raw = file.read_bytes()
        total += len(raw)
        if total > MAX_TOTAL_BYTES or b"\0" in raw:
            raise ValueError("Document bytes exceed bounds or contain binary content")
        for start, end, text in sections(raw.decode("utf-8")):
            prepared.append((path, start, end, text))
            if len(prepared) > MAX_SECTIONS:
                raise ValueError("Document section count exceeds bounds")
    # Read trusted tracked Python files only; resolve against current indexed symbols.
    texts, python_bytes = {}, 0
    for path in sorted(tracked):
        if not path.endswith(".py"):
            continue
        cfg.path(path)
        file = cfg.repo_root / path
        if file.is_symlink() or file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Unsafe Python input for reference resolution")
        python_bytes += file.stat().st_size
        if len(texts) >= 2000 or python_bytes > 20_000_000:
            raise ValueError("Python reference corpus exceeds bounds")
        # tokenize honors PEP 263, as sync does.
        with tokenize.open(file) as stream:
            texts[path] = stream.read()
    symbols = store.query(
        "MATCH (s:Symbol {repo_id:$repo, revision:$sha, current:true}) "
        "RETURN s.uid AS uid, s.path AS path, s.qualname AS qualname LIMIT 20001",
        {"repo": cfg.repo_id, "sha": sha},
    )
    if len(symbols) > 20000:
        raise ValueError("Indexed symbol count exceeds bounds")
    resolve = symbol_resolver(texts, symbols)
    prs = store.query(
        "MATCH (p:PR {repo_id:$repo}) RETURN p.uid AS uid, p.number AS number LIMIT 10001",
        {"repo": cfg.repo_id},
    )
    if len(prs) > 10000:
        raise ValueError("PR reference corpus exceeds bounds")
    by_number = defaultdict(list)
    for pr in prs:
        by_number[pr["number"]].append(pr["uid"])
    if not clean(cfg.repo_root) or revision(cfg.repo_root) != sha or store.revision() != state:
        raise ValueError("Checkout or index changed during document preparation")
    symbol_links = pr_links = 0
    unresolved = set()
    for path, start, end, text in prepared:
        uid = f"{cfg.repo_id}@{sha}:{path}:section:L{start}-L{end}"
        source = uid + ":source"
        props = {
            "repo_id": cfg.repo_id,
            "revision": sha,
            "path": path,
            "line_start": start,
            "line_end": end,
            "digest": hashlib.sha256(text.encode()).hexdigest(),
            "source_kind": "repository_document",
        }
        store.upsert("Document", uid, {**props, "text": text})
        store.upsert(
            "Source",
            source,
            {
                **props,
                "excerpt": text,
                "uri": f"{cfg.repo_url}/blob/{sha}/{path}#L{start}-L{end}",
            },
        )
        store.edge(uid, "SUPPORTS", source)
        # Refresh only our exact mentions, including newly resolvable PRs on rerun.
        store.query("MATCH (d:Document {uid:$uid})-[r:MENTIONS]->() DELETE r", {"uid": uid})
        links = {}
        for offset, line in enumerate(text.splitlines(), start):
            for number in issue_mentions(line, cfg.repo_url):
                candidates = by_number.get(number, [])
                if len(candidates) == 1:
                    links.setdefault(candidates[0], (offset, f"#{number}", "exact_pr_number"))
            for match in REFERENCES.finditer(line):
                reference = next(v for v in match.groups() if v)
                target = resolve(reference)
                if target:
                    links.setdefault(target, (offset, reference, "exact_reference"))
                else:
                    unresolved.add(reference)
        for target, (line, reference, confidence) in links.items():
            store.edge(
                uid,
                "MENTIONS",
                target,
                {
                    "source_uid": source,
                    "source_line": line,
                    "reference": reference,
                    "confidence": confidence,
                    "binding": False,
                    "revision": sha,
                    "basis": "repository_document_exact_mention",
                },
            )
            pr_links += confidence == "exact_pr_number"
            symbol_links += confidence == "exact_reference"
    if not clean(cfg.repo_root) or revision(cfg.repo_root) != sha or store.revision() != state:
        raise ValueError("Checkout or index changed; rerun before using document evidence")
    return {
        "revision": sha,
        "files": len(paths),
        "sections": len(prepared),
        "pr_links": pr_links,
        "symbol_links": symbol_links,
        "unresolved_references": sorted(unresolved),
        "binding": False,
        "symbol_link_status": "verified" if symbol_links else "no_verified_symbol_link",
    }
