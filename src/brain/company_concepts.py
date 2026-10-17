"""Source-checked label associations; matching a mention does not resolve identity."""

import json

from .ingest.concepts import concept_key, validate_mentions
from .memory import canonical, citations, digest


def concept_mentions(store, entities, sha):
    """Caller must first authorize company access. Returns only current grounded mentions."""
    keys = sorted({concept_key(n["name"]) for n in entities})
    if not keys:
        return [], []
    rows = store.query(
        "MATCH (d:Document {repo_id:$repo,revision:$sha,current:true})"
        "-[:MENTIONS_CONCEPT]->(c:ConceptMention {repo_id:$repo,revision:$sha,current:true})"
        "-[:SUPPORTED_BY]->(s:Source {repo_id:$repo,revision:$sha}) "
        "MATCH (d)-[:SUPPORTS]->(s) "
        "WHERE c.key IN $keys AND c.source_uid=s.uid AND c.document_uid=d.uid "
        "RETURN properties(c) AS mention, d.uid AS document_uid, d.path AS path, "
        "d.line_start AS line_start, d.line_end AS line_end, d.digest AS digest, "
        "substring(coalesce(d.text,''),0,12001) AS text, size(coalesce(d.text,'')) AS original_chars, "
        "d.concepts_json AS annotations, d.concepts_source_digest AS annotation_digest, "
        "s.uid AS source_uid, s.uri AS uri, substring(coalesce(s.excerpt,''),0,12001) AS excerpt, "
        "size(coalesce(s.excerpt,'')) AS source_chars ORDER BY document_uid,c.uid LIMIT 101",
        {"repo": store.cfg.repo_id, "sha": sha, "keys": keys},
    )
    if len(rows) > 100:
        raise ValueError("Company concept candidate bound exceeded; narrow requested memories")
    verified, unresolved = [], []
    seen = set()
    for row in rows:
        mention = row["mention"]
        try:
            if (
                row["original_chars"] != row["source_chars"]
                or not 0 < row["original_chars"] <= 12000
                or len(row["text"]) != row["original_chars"]
                or row["text"] != row["excerpt"]
                or digest(row["text"]) != row["digest"]
                or row["digest"] != row["annotation_digest"]
                or mention["evidence_digest"] != row["digest"]
                or len(row["annotations"] or "") > 100000
            ):
                raise ValueError("Changed concept evidence")
            annotations = json.loads(row["annotations"])
            item = {k: mention[k] for k in ("document", "name", "start", "end")}
            checked = validate_mentions(
                [{"uid": row["document_uid"], "text": row["text"]}], {"items": [item]}
            )[0]
            expected_uid = (
                row["document_uid"]
                + ":concept:"
                + digest(canonical([item["name"], item["start"], item["end"]]))
            )
            if (
                mention["uid"] != expected_uid
                or mention["key"] != checked["key"]
                or mention not in annotations
                or mention["document"] != row["document_uid"]
                or mention["document_uid"] != row["document_uid"]
                or mention["source_uid"] != row["source_uid"]
                or mention["key"] not in keys
            ):
                raise ValueError("Concept annotation does not match native evidence")
            proof = [{"uri": row["uri"], "digest": row["digest"]}]
            citations(proof)
        except (ValueError, KeyError, TypeError):
            unresolved.append(
                {
                    "uid": mention.get("uid", ""),
                    "kind": "ConceptMention",
                    "reason": "concept_source_span_unverified",
                }
            )
            continue
        if mention["uid"] in seen:
            # Multiple source paths are ambiguous even when bytes happen to agree.
            unresolved.append(
                {
                    "uid": mention["uid"],
                    "kind": "ConceptMention",
                    "reason": "ambiguous_concept_source",
                }
            )
            verified = [r for r in verified if r["mention"]["uid"] != mention["uid"]]
            continue
        seen.add(mention["uid"])
        verified.append({**row, "proof": proof})
    return verified, unresolved
