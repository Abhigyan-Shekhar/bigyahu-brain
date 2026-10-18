"""Bounded workspace navigation using current company evidence, never memory ACL bypasses."""

from .evidence import code_evidence, native_graph, ready, source_evidence

FOLDER = "CASE WHEN coalesce(n.path,'')='' THEN '(no path)' WHEN size(split(n.path,'/'))>1 THEN split(n.path,'/')[0] ELSE '(root)' END"


def overview(store, grouping):
    sha = ready(store)
    if grouping not in {"type", "folder"}:
        raise ValueError("Choose type or folder grouping")
    expression = "labels(n)[0]" if grouping == "type" else FOLDER
    groups = store.query(
        "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) "
        f"WITH {expression} AS key,count(n) AS count "
        "RETURN key,count ORDER BY count DESC,key LIMIT 101",
        {"repo": store.cfg.repo_id},
    )
    totals = store.query(
        "MATCH (n {repo_id:$repo}) WHERE coalesce(n.current,true) RETURN count(n) AS nodes",
        {"repo": store.cfg.repo_id},
    )
    target_expression = expression.replace("n.", "m.").replace("labels(n)", "labels(m)")
    links = store.query(
        "MATCH (n {repo_id:$repo})-[r]->(m {repo_id:$repo}) "
        "WHERE coalesce(n.current,true) AND coalesce(m.current,true) "
        f"WITH {expression} AS source,{target_expression} AS target,"
        "type(r) AS relation,count(r) AS count "
        "RETURN source,target,relation,count ORDER BY count DESC,source,target,relation LIMIT 201",
        {"repo": store.cfg.repo_id},
    )
    return {
        "relationships": links[:200],
        "relationships_truncated": len(links) > 200,
        "relationship_limit": 200,
        "grouping": grouping,
        "groups": groups[:100],
        "total_nodes": totals[0]["nodes"],
        "truncated": len(groups) > 100,
        "group_limit": 100,
        "revision": sha,
    }


def inspect_node(store, uid):
    sha = ready(store)
    rows = store.query(
        "MATCH (n {repo_id:$repo,uid:$uid}) WHERE coalesce(n.current,true) "
        "RETURN n.path AS path,n.qualname AS qualname,n.uri AS uri,n.revision AS revision,"
        "coalesce(n.line_start,n.start_line,n.lineno,1) AS start,n.source_kind AS source_kind LIMIT 1",
        {"repo": store.cfg.repo_id, "uid": uid},
    )
    if not rows:
        raise KeyError("Current company entity unavailable")
    topology = native_graph(store, [uid])
    node = topology["nodes"][0]
    sources = store.query(
        "MATCH (n {repo_id:$repo,uid:$uid})-[:SUPPORTS|SUPPORTED_BY]->(s:Source {repo_id:$repo}) "
        "RETURN DISTINCT s.uid AS uid ORDER BY uid LIMIT 11",
        {"repo": store.cfg.repo_id, "uid": uid},
    )
    result = {
        "node": node,
        "properties": rows[0],
        "revision": sha,
        "sources": [r["uid"] for r in sources[:10]],
        "sources_truncated": len(sources) > 10,
    }
    try:
        if "Source" in node["labels"]:
            result["evidence"] = source_evidence(store, uid)
        elif set(node["labels"]) & {"File", "Symbol"} and rows[0]["path"]:
            start = int(rows[0]["start"])
            result["evidence"] = code_evidence(store, rows[0]["path"], start, start + 79)
        elif sources:
            result["evidence"] = source_evidence(store, sources[0]["uid"])
        else:
            result["source_notice"] = (
                "No directly reopenable source is attached to this entity. Explore its recorded neighbors."
            )
    except (ValueError, OSError) as exc:
        result["source_notice"] = (
            str(exc)[:500] if isinstance(exc, ValueError) else "Source bytes unavailable"
        )
    return result
