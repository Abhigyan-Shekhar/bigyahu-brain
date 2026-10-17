"""Bounded lexical bug similarity, native path associations and checked Git patches."""

import json
import math
import re
import subprocess
from collections import Counter

from ..ingest.git_parser import git
from ..memory import digest
from .evidence import native_graph, ready, register, source_evidence


def tokens(text):
    return set(re.findall(r"[a-z0-9_]{2,80}", text.casefold()))


def patch_evidence(store, commit, path):
    sha = ready(store)
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid historical commit")
    path = store.cfg.path(path)
    # A client-selected object must be indexed and reachable, not an arbitrary ref.
    uid = store.cfg.repo_id + ":commit:" + commit
    if not store.query(
        "MATCH (c:Commit {repo_id:$repo,uid:$uid}) RETURN c.uid AS uid",
        {"repo": store.cfg.repo_id, "uid": uid},
    ):
        raise ValueError("Commit is not indexed")
    git(store.cfg.repo_root, "merge-base", "--is-ancestor", commit, sha)
    raw = git(
        store.cfg.repo_root,
        "show",
        "--format=",
        "--no-ext-diff",
        "--no-textconv",
        "--unified=3",
        commit,
        "--",
        path,
    )
    if not raw:
        raise ValueError("Historical patch is unavailable")
    text = raw[:12000]
    files = store.query(
        "MATCH (c:Commit {repo_id:$repo,uid:$uid})-[:MODIFIES]->(f:File {repo_id:$repo,current:true,revision:$sha,path:$path}) RETURN f.uid AS uid",
        {"repo": store.cfg.repo_id, "uid": uid, "sha": sha, "path": path},
    )
    symbols = (
        store.query(
            "MATCH (f:File {repo_id:$repo,current:true,revision:$sha})-[:DECLARES]->(s:Symbol {repo_id:$repo,current:true,revision:$sha}) WHERE f.uid IN $files RETURN DISTINCT s.uid AS uid ORDER BY uid LIMIT 21",
            {"repo": store.cfg.repo_id, "sha": sha, "files": [f["uid"] for f in files]},
        )
        if files
        else []
    )
    graph = native_graph(
        store, [uid] + [f["uid"] for f in files] + [s["uid"] for s in symbols[:20]]
    )
    return {
        "kind": "history_diff",
        "ref": {"commit": commit, "path": path},
        "title": f"{path} · patch {commit[:12]}",
        "text": text,
        "digest": digest(text),
        "revision": sha,
        "uri": f"{store.cfg.repo_url}/commit/{commit}",
        "graph": graph,
        "association_status": "current_file_link" if files else "current_file_link_missing",
        "association_basis": "historical_file_path_not_function_change_proof",
        "symbols_truncated": len(symbols) > 20,
        "truncated": len(raw) > len(text),
        "verification": "indexed_reachable_git_patch",
        "binding": False,
    }


def search(store, folder, query="", files=None, symbols=None):
    ready(store)
    files, symbols = files or [], symbols or []
    if len(query) > 2000 or len(files) > 12 or len(symbols) > 12:
        raise ValueError("History accepts 2000 query characters and twelve file/symbol hints")
    files = [store.cfg.path(p) for p in files]
    if any(not isinstance(s, str) or len(s) > 300 for s in symbols):
        raise ValueError("Invalid symbol hint")
    params = {"repo": store.cfg.repo_id}
    coverage = store.query(
        "MATCH (p:Project {uid:$repo}) RETURN p.github_cursor AS github_cursor,p.github_syncing AS github_syncing,p.github_initial_coverage AS initial_coverage",
        params,
    )
    counts = store.query(
        "MATCH (w {repo_id:$repo}) WHERE w:Commit OR w:Issue OR w:PR RETURN labels(w)[0] AS kind,count(w) AS count",
        params,
    )
    rows = store.query(
        "MATCH p=(w {repo_id:$repo})-[:SUPPORTS|DISCUSSED_IN*1..2]->(s:Source {repo_id:$repo}) WHERE (w:Commit OR w:Issue OR w:PR) AND all(n IN nodes(p) WHERE n.repo_id=$repo) "
        "OPTIONAL MATCH (w)-[:MODIFIES|CHANGES]->(f:File {repo_id:$repo,current:true}) "
        "RETURN w.uid AS uid,w.sha AS sha,s.uid AS source_uid,s.uri AS source_uri,coalesce(w.title,'') AS title,substring(coalesce(s.excerpt,''),0,12000) AS text,coalesce(w.timestamp,w.snapshot_at,'') AS timestamp,collect(DISTINCT f.path)[0..40] AS paths ORDER BY uid,source_uid LIMIT 1001",
        params,
    )
    warnings = []
    acquisition = None
    if coverage and not coverage[0].get("github_cursor") and coverage[0].get("initial_coverage"):
        acquisition = json.loads(coverage[0]["initial_coverage"])
        warnings.append("github_history_partial_initial_sample")
    elif not coverage or not coverage[0].get("github_cursor"):
        warnings.append("github_issue_pr_coverage_unverified")
    if coverage and coverage[0].get("github_syncing"):
        return {
            "status": "incomplete",
            "items": [],
            "checked_evidence": [],
            "warnings": ["github_refresh_in_progress"],
        }
    if len(rows) > 1000:
        return {
            "status": "incomplete",
            "items": [],
            "checked_evidence": [],
            "warnings": [*warnings, "history_candidate_bound"],
            "coverage": counts,
        }
    if symbols:
        associated = store.query(
            "MATCH (s:Symbol {repo_id:$repo,current:true}) WHERE s.uid IN $symbols OR s.qualname IN $symbols RETURN DISTINCT s.path AS path ORDER BY path LIMIT 13",
            {**params, "symbols": symbols},
        )
        if len(associated) > 12:
            raise ValueError("Symbol hints match too many files; use explicit file hints")
        files = sorted(set(files) | {r["path"] for r in associated})
    terms = tokens(query + " " + " ".join(symbols))
    # Frequency is per work item: ten comments must not count as ten bugs.
    groups = {}
    for row in rows:
        groups.setdefault(row["uid"], []).append(row)
    documents = {
        uid: set().union(*(tokens(r["title"] + " " + r["text"]) for r in sources))
        for uid, sources in groups.items()
    }
    frequency = Counter(t for doc in documents.values() for t in doc)

    def term_score(matched):
        return sum(math.log(1 + len(groups) / (1 + frequency[t])) for t in matched)

    ranked = []
    for uid, sources in groups.items():
        matched = sorted(terms & documents[uid])
        paths = sorted(set().union(*(set(r["paths"]) for r in sources)))
        matched_files = sorted(set(paths) & set(files))
        score = term_score(matched) + 4 * len(matched_files)
        if (terms or files) and score == 0:
            continue
        supports = []
        for source in sources:
            source_terms = sorted(terms & tokens(source["title"] + " " + source["text"]))
            if source_terms or matched_files or not (terms or files):
                supports.append({**source, "source_score": round(term_score(source_terms), 6)})
        supports.sort(key=lambda r: (-r["source_score"], r["source_uid"]))
        ranked.append(
            {
                **sources[0],
                "paths": paths,
                "score": round(score, 6),
                "matched_terms": matched,
                "matched_files": matched_files,
                "supports": supports,
                "association_basis": "historical_file_path_not_function_change_proof",
            }
        )
    ranked.sort(key=lambda r: (-r["score"], r["uid"]))
    checked, items = [], []
    for row in ranked[:10]:
        proofs = []
        support_sources = []
        for source in row["supports"]:
            link = {
                "source_uid": source["source_uid"],
                "uri": source["source_uri"],
                "score": source["source_score"],
            }
            if len(proofs) < 3:
                try:
                    proof = register(folder, source_evidence(store, source["source_uid"]))
                    proofs.append(proof)
                    checked.append(proof)
                    link["evidence_id"] = proof["id"]
                except (ValueError, OSError, UnicodeError):
                    warnings.append("historical_source_unavailable")
            support_sources.append(link)
        if not proofs:
            continue
        patches = []
        if row["sha"]:
            for path in (row["matched_files"] or row["paths"])[:2]:
                try:
                    patch = register(folder, patch_evidence(store, row["sha"], path))
                    checked.append(patch)
                    patches.append(patch["id"])
                except (ValueError, OSError, subprocess.SubprocessError):
                    warnings.append("historical_patch_unavailable")
        related = store.query(
            "MATCH (w {uid:$uid,repo_id:$repo})-[r:REFERENCES]-(other {repo_id:$repo}) RETURN other.uid AS uid,type(r) AS relation ORDER BY uid LIMIT 11",
            {**params, "uid": row["uid"]},
        )
        symbols_now = store.query(
            "MATCH (f:File {repo_id:$repo,current:true})-[:DECLARES]->(s:Symbol {repo_id:$repo,current:true}) WHERE f.path IN $paths RETURN s.uid AS uid,s.qualname AS name,s.path AS path ORDER BY uid LIMIT 21",
            {**params, "paths": row["paths"]},
        )
        items.append(
            {k: v for k, v in row.items() if k not in {"text", "supports"}}
            | {
                "message_evidence_id": proofs[0]["id"],
                "support_evidence_ids": [p["id"] for p in proofs],
                "support_sources": support_sources,
                "support_excerpts_bounded": len(support_sources) > len(proofs),
                "patch_evidence_ids": patches,
                "related_work": related[:10],
                "current_file_symbols": symbols_now[:20],
                "rationale_status": "requires_reasoning_and_regression_validation",
            }
        )
    return {
        "status": "ok",
        "items": items,
        "truncated": len(ranked) > 10,
        "checked_evidence": checked,
        "coverage": counts,
        "acquisition_coverage": acquisition,
        "warnings": sorted(set(warnings)),
        "ranking": "rare_term_overlap_plus_explicit_file_association",
        "binding": False,
    }
