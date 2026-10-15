"""Bounded source delivery shared by context and change checks."""

SOURCE_FIELDS = (
    "RETURN DISTINCT s.uid AS source_uid, s.uri AS uri, "
    "substring(coalesce(s.excerpt,''),0,$chars) AS text, "
    "size(coalesce(s.excerpt,'')) AS original_chars, "
    "s.revision AS revision, s.revision_basis AS revision_basis, "
    "s.snapshot_at AS snapshot_at, s.work_uid AS work_uid, "
    "s.work_type AS work_type, s.work_status AS work_status, "
    "s.status_basis AS status_basis, s.merged_at AS merged_at "
    "ORDER BY source_uid LIMIT 21"
)
LIMITS = {"sources": 20, "excerpt_chars": 2000, "total_excerpt_chars": 12000}


def bound_excerpts(sources, repo, scope="org", prefix=()):
    """Deduplicate sources; decision prose shares the same text/count budget."""
    excerpts, truncated, seen = [], set(), set()
    remaining = LIMITS["total_excerpt_chars"]
    for original in [*prefix, *sources]:
        source = dict(original)
        key = (source.get("source_uid"), source.get("decision_id"))
        if key in seen:
            continue
        seen.add(key)
        if len(excerpts) >= LIMITS["sources"] or remaining <= 0:
            truncated.add("sources" if remaining > 0 else "total_excerpt_chars")
            continue
        text = source.get("text") or ""
        original_chars = source.get("original_chars", len(text))
        source["text"] = text[: min(remaining, LIMITS["excerpt_chars"])]
        source["truncated"] = len(source["text"]) < original_chars
        if source["truncated"]:
            truncated.add("total_excerpt_chars" if remaining < len(text) else "excerpt_chars")
        remaining -= len(source["text"])
        source.update(scope=scope, repo_id=repo, trust_status="untrusted_evidence", binding=False)
        if source.get("source_uid"):
            source["evidence_confidence"] = (
                "recorded_source" if source.get("uri") else "provenance_incomplete"
            )
            for field in ("revision_basis", "work_status", "status_basis"):
                source[field] = source.get(field) or "unknown"
        excerpts.append(source)
    return excerpts, truncated


def source_routes():
    return [
        ("exact_source", "MATCH (s:Source {repo_id:$repo}) WHERE s.uid IN $ids "),
        (
            "direct_source_link",
            (
                "MATCH (a {repo_id:$repo})-[:SUPPORTS|SUPPORTED_BY]->"
                "(s:Source {repo_id:$repo}) WHERE a.uid IN $ids "
            ),
        ),
        (
            "discussion_source_link",
            (
                "MATCH (a {repo_id:$repo})-[:DISCUSSED_IN]->"
                "(c:Comment {repo_id:$repo})-[:SUPPORTS]->(s:Source {repo_id:$repo}) "
                "WHERE a.uid IN $ids "
            ),
        ),
    ]
