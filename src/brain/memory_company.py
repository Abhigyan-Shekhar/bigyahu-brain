"""Verified company evidence projections, never inferred policy or identity joins.

Only an explicitly authorized projection can join selected memory references to
the configured repository. Original company nodes are not modified. Proxies and
native edges live in the memory namespace and retain original node UIDs/revision.
"""

from collections import defaultdict
from pathlib import PurePosixPath

from .graph import GraphUnavailable
from .memory import canonical, digest


class CompanyBridge:
    def __init__(self, memory, store):
        if (
            not store.cfg.tenant_id
            or memory.identity.tenant != store.cfg.tenant_id
            or memory.identity.principal != store.cfg.principal
        ):
            raise ValueError("Company bridge and catalog identities must match")
        self.memory, self.store = memory, store

    def state(self):
        self.memory.authorize("company")
        state = self.store.revision()
        if not state["sha"] or state["syncing"]:
            raise GraphUnavailable("Company graph has no completed sync")
        return state

    def snapshot(self, brain, slot, memory_nodes):
        """Resolve current eligible references; caller holds a catalog transaction."""
        state = self.state()
        sha, repo = state["sha"], self.store.cfg.repo_id
        nodes, edges, unresolved = {}, {}, []

        def proxy(kind, original, **props):
            uid = slot + ":Company:" + digest(canonical([repo, sha, kind, original]))
            nodes[uid] = {
                "uid": uid,
                "kind": "Company" + kind,
                "brain": brain,
                "company_uid": original,
                "company_repo": repo,
                "graph_revision": sha,
                **props,
            }
            return uid

        def edge(a, relation, b, basis, evidence=()):
            edges[a, relation, b] = {
                "source": a,
                "relation": relation,
                "target": b,
                "basis": basis,
                "assertion_uid": "",
                "state": "",
                "evidence_json": canonical(list(evidence)),
            }

        sources = [n for n in memory_nodes if n["kind"] == "Source"]
        entities = [n for n in memory_nodes if n["kind"] == "Entity"]
        params = {"repo": repo, "sha": sha}
        verified = {}
        if sources:
            candidates = self.store.query(
                "MATCH (s:Source {repo_id:$repo}) WHERE s.uri IN $uris "
                "RETURN s.uid AS uid, s.uri AS uri, substring(coalesce(s.excerpt,''),0,12001) AS text, "
                "size(coalesce(s.excerpt,'')) AS original_chars, s.revision AS source_revision "
                "ORDER BY uid LIMIT 1001",
                {**params, "uris": sorted({n["uri"] for n in sources})},
            )
            if len(candidates) > 1000:
                raise ValueError("Company source candidate bound exceeded")
            by_uri = defaultdict(list)
            for row in candidates:
                if 0 < row["original_chars"] <= 12000 and len(row["text"]) == row["original_chars"]:
                    by_uri[row["uri"]].append(row)
            for reference in sources:
                matches = [
                    r for r in by_uri[reference["uri"]] if digest(r["text"]) == reference["digest"]
                ]
                if len(matches) != 1:
                    unresolved.append(
                        {
                            "uid": reference["uid"],
                            "kind": "Source",
                            "reason": "source_not_unique_or_digest_unverified",
                        }
                    )
                    continue
                row = matches[0]
                proof = [{"uri": row["uri"], "digest": reference["digest"]}]
                target = proxy(
                    "Source",
                    row["uid"],
                    uri=row["uri"],
                    digest=reference["digest"],
                    text=row["text"],
                    source_revision=row["source_revision"],
                )
                edge(
                    reference["uid"],
                    "VERIFIED_SOURCE",
                    target,
                    "exact_uri_and_verified_bytes",
                    proof,
                )
                verified[row["uid"]] = {**row, "proxy": target, "proof": proof}

        # These are lexical code identities, not runtime binding/import claims.
        # Bare names and ambiguous module names are intentionally not resolved.
        symbols, files = [], []
        if entities or verified:
            symbols = self.store.query(
                "MATCH (s:Symbol {repo_id:$repo,revision:$sha,current:true}) "
                "RETURN s.uid AS uid, s.path AS path, s.qualname AS qualname, "
                "s.kind AS kind, s.lineno AS line_start, s.end_lineno AS line_end "
                "ORDER BY uid LIMIT 20001",
                params,
            )
            files = self.store.query(
                "MATCH (f:File {repo_id:$repo,revision:$sha,current:true}) "
                "RETURN f.uid AS uid, f.path AS path ORDER BY uid LIMIT 5001",
                params,
            )
            if len(symbols) > 20000 or len(files) > 5000:
                raise ValueError("Company code lookup bound exceeded")
        grouped_files = defaultdict(list)
        for file in files:
            if file["uid"] == f"{repo}@{sha}:{file['path']}":
                grouped_files[file["path"]].append(file)
        by_path = {path: rows[0] for path, rows in grouped_files.items() if len(rows) == 1}
        module_paths = defaultdict(set)
        for path in by_path:
            if path.endswith(".py"):
                parts = list(PurePosixPath(path).with_suffix("").parts)
                if parts[0] == "src":
                    parts.pop(0)
                if parts and parts[-1] == "__init__":
                    parts.pop()
                module_paths[".".join(parts)].add(path)
        modules_by_path = {
            next(iter(paths)): module for module, paths in module_paths.items() if len(paths) == 1
        }
        lookup, by_uid = defaultdict(list), {}
        for symbol in symbols:
            path, qual = symbol["path"], symbol["qualname"]
            if path not in by_path or symbol["uid"] != f"{repo}@{sha}:{path}::{qual}":
                continue
            by_uid[symbol["uid"]] = symbol
            lookup[path + "::" + qual].append(symbol)
            if path in modules_by_path:
                lookup[modules_by_path[path] + "." + qual].append(symbol)

        symbol_cache = {}

        def symbol_proxy(row):
            if row["uid"] in symbol_cache:
                return symbol_cache[row["uid"]]
            uid = proxy(
                "Symbol",
                row["uid"],
                path=row["path"],
                qualname=row["qualname"],
                line_start=row["line_start"],
                line_end=row["line_end"],
            )
            file = by_path[row["path"]]
            parent = proxy("File", file["uid"], path=file["path"])
            # Copy only an existing native declaration, never manufacture one.
            declared = self.store.query(
                "MATCH (f:File {uid:$file,repo_id:$repo,revision:$sha,current:true})"
                "-[:DECLARES]->(s:Symbol {uid:$symbol,repo_id:$repo,revision:$sha,current:true}) "
                "RETURN s.uid AS uid LIMIT 1",
                {**params, "file": file["uid"], "symbol": row["uid"]},
            )
            if declared:
                edge(parent, "DECLARES", uid, "company_native_declaration")
            symbol_cache[row["uid"]] = uid
            return uid

        for reference in entities:
            matches = lookup[reference["name"]]
            if len(matches) != 1:
                unresolved.append(
                    {
                        "uid": reference["uid"],
                        "kind": "Entity",
                        "reason": "no_unique_explicit_lexical_symbol",
                    }
                )
                continue
            edge(
                reference["uid"],
                "RESOLVES_TO",
                symbol_proxy(matches[0]),
                "exact_indexed_lexical_identity",
            )

        if verified:
            documents = self.store.query(
                "MATCH (d:Document {repo_id:$repo,revision:$sha,current:true})"
                "-[:SUPPORTS]->(src:Source {repo_id:$repo}) WHERE src.uid IN $sources "
                "OPTIONAL MATCH (d)-[r:MENTIONS]->"
                "(s:Symbol {repo_id:$repo,revision:$sha,current:true}) "
                "RETURN d.uid AS uid, d.path AS path, d.line_start AS line_start, "
                "d.line_end AS line_end, substring(coalesce(d.text,''),0,12001) AS text, "
                "size(coalesce(d.text,'')) AS original_chars, src.uid AS source_uid, "
                "s.uid AS symbol_uid, r.confidence AS confidence, r.source_uid AS evidence_uid "
                "ORDER BY uid,symbol_uid LIMIT 501",
                {**params, "sources": sorted(verified)},
            )
            if len(documents) > 500:
                raise ValueError("Company document path bound exceeded")
            for row in documents:
                source = verified[row["source_uid"]]
                if row["original_chars"] > 12000 or row["text"] != source["text"]:
                    unresolved.append(
                        {
                            "uid": row["uid"],
                            "kind": "Document",
                            "reason": "document_source_bytes_mismatch",
                        }
                    )
                    continue
                document = proxy(
                    "Document",
                    row["uid"],
                    path=row["path"],
                    text=row["text"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                )
                edge(
                    document,
                    "SUPPORTS",
                    source["proxy"],
                    "company_native_document_source",
                    source["proof"],
                )
                if (
                    row["symbol_uid"] in by_uid
                    and row["confidence"] == "exact_reference"
                    and row["evidence_uid"] == row["source_uid"]
                ):
                    edge(
                        document,
                        "MENTIONS",
                        symbol_proxy(by_uid[row["symbol_uid"]]),
                        "company_native_document_mention",
                        source["proof"],
                    )
        # Named semantic concepts use source-grounded mention associations only.
        # They never become lexical symbol identities or binding constraints.
        if entities:
            from .company_concepts import concept_mentions
            from .ingest.concepts import concept_key

            mentions, rejected = concept_mentions(self.store, entities, sha)
            unresolved.extend(rejected)
            for row in mentions:
                mention = row["mention"]
                target = proxy(
                    "ConceptMention",
                    mention["uid"],
                    name=mention["name"],
                    text=mention["name"],
                    model=mention["model"],
                    path=row["path"],
                    start=mention["start"],
                    end=mention["end"],
                    association="literal_concept_mention_not_identity",
                )
                source = proxy(
                    "Source",
                    row["source_uid"],
                    uri=row["uri"],
                    digest=row["digest"],
                    text=row["text"],
                    source_revision=sha,
                )
                document = proxy(
                    "Document",
                    row["document_uid"],
                    path=row["path"],
                    text=row["text"],
                    line_start=row["line_start"],
                    line_end=row["line_end"],
                )
                edge(document, "SUPPORTS", source, "company_native_document_source", row["proof"])
                edge(
                    document,
                    "MENTIONS_CONCEPT",
                    target,
                    "model_selected_literal_span",
                    row["proof"],
                )
                edge(target, "SUPPORTED_BY", source, "exact_document_bytes", row["proof"])
                for reference in entities:
                    if concept_key(reference["name"]) == mention["key"]:
                        edge(
                            reference["uid"],
                            "MATCHES_MENTION",
                            target,
                            "unicode_casefold_whitespace_label_association",
                            row["proof"],
                        )
        if self.state() != state:
            raise GraphUnavailable("Company graph changed during reference resolution")
        if len(nodes) > 500 or len(edges) > 1000:
            raise ValueError("Company projection exceeds 500 nodes or 1000 edges")
        return {
            "nodes": list(nodes.values()),
            "edges": list(edges.values()),
            "revision": sha,
            "unresolved": unresolved,
        }
