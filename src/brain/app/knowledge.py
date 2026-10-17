"""Literal, source-backed document/code associations; never inferred constraints."""

import re
from collections import Counter


def link_sources(store, source_ids):
    params = {"repo": store.cfg.repo_id, "sources": source_ids}
    documents = store.query(
        "MATCH (d:Document {repo_id:$repo,current:true})-[:SUPPORTS]->(s:Source) "
        "WHERE s.uid IN $sources RETURN d.uid AS uid,d.text AS text,s.uid AS source",
        params,
    )
    targets = store.query(
        "MATCH (n {repo_id:$repo}) WHERE (n:File OR n:Symbol) AND coalesce(n.current,true) "
        "RETURN n.uid AS uid,n.path AS path,n.qualname AS qualname,labels(n) AS labels ORDER BY uid LIMIT 10001",
        params,
    )
    qualified_counts = Counter(t.get("qualname") for t in targets if "Symbol" in t["labels"])
    mentions = []
    for doc in documents:
        for target in targets[:10000]:
            if "Symbol" in target["labels"] and (
                len(targets) > 10000 or qualified_counts[target.get("qualname")] != 1
            ):
                continue
            # A bare short function name is not sufficient to establish identity.
            names = (
                [target.get("qualname")] if "Symbol" in target["labels"] else [target.get("path")]
            )
            for name in names:
                if not name or ("/" not in name and "." not in name):
                    continue
                if re.search(r"(?<![\w./])" + re.escape(name) + r"(?![\w/]|\.[\w/])", doc["text"]):
                    mentions.append(
                        {
                            "a": doc["uid"],
                            "b": target["uid"],
                            "source": doc["source"],
                            "quote": name,
                        }
                    )
                    break
    store.query(
        "UNWIND $mentions AS item MATCH (d:Document {uid:item.a,repo_id:$repo}), "
        "(n {uid:item.b,repo_id:$repo}) MERGE (d)-[r:MENTIONS]->(n) "
        "SET r.binding=false,r.basis='literal_code_reference',r.source_uid=item.source,r.quote=item.quote",
        {**params, "mentions": mentions},
    )
    return {"code_links": len(mentions), "code_link_coverage_truncated": len(targets) > 10000}
