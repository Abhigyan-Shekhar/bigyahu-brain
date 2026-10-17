"""Bounded native frontier expansion without variable-length path enumeration."""

from collections import defaultdict


def frontier_paths(store, seeds, nodes, edges, memory_ids, types, budget=10000):
    expected = {
        (e["source"], e["relation"], e["target"], e.get("assertion_uid", "")) for e in edges
    }
    seen = {seed: {seed} for seed in seeds}
    active = {seed: {seed: ([seed], [], [], [])} for seed in seeds}
    paths, visits, queries = [], len(seeds), 0
    for _depth in range(4):
        frontier = sorted({uid for wave in active.values() for uid in wave})
        if not frontier:
            break
        rows = store.memory_query(
            "MATCH (a:MemoryNode)-[r]-(b:MemoryNode) "
            "WHERE a.uid IN $frontier AND a.uid IN $allowed AND b.uid IN $allowed "
            "AND type(r) IN $types "
            "AND (coalesce(r.assertion_uid,'')='' OR r.assertion_uid IN $assertions) "
            "RETURN a.uid AS source, b.uid AS target, type(r) AS relation, "
            "startNode(r).uid AS origin, coalesce(r.assertion_uid,'') AS assertion_uid "
            "ORDER BY source,relation,target,assertion_uid,origin LIMIT 4001",
            {
                "frontier": frontier,
                "allowed": sorted(nodes),
                "types": sorted(types),
                "assertions": sorted({e[3] for e in expected if e[3]}),
            },
        )
        queries += 1
        if len(rows) > 4000:
            return [], {
                "status": "incomplete",
                "reason": "native_frontier_edge_bound_exceeded",
                "visited_states": visits,
                "frontier_queries": queries,
            }
        adjacency = defaultdict(list)
        observed = set()
        for row in rows:
            a, b, relation, assertion = (
                row[k] for k in ("source", "target", "relation", "assertion_uid")
            )
            forward = row["origin"] == a
            actual = (a, relation, b, assertion) if forward else (b, relation, a, assertion)
            if (
                a not in frontier
                or a not in nodes
                or b not in nodes
                or relation not in types
                or row["origin"] not in {a, b}
                or actual not in expected
            ):
                return [], {
                    "status": "incomplete",
                    "reason": "retrieval_path_projection_mismatch",
                    "visited_states": visits,
                    "frontier_queries": queries,
                }
            observed.add(actual)
            adjacency[a].append((b, relation, assertion, "outgoing" if forward else "incoming"))
        required = {e for e in expected if e[1] in types and (e[0] in frontier or e[2] in frontier)}
        if observed != required:
            return [], {
                "status": "incomplete",
                "reason": "retrieval_path_projection_mismatch",
                "visited_states": visits,
                "frontier_queries": queries,
            }
        following = {}
        for seed, wave in sorted(active.items()):
            following[seed] = {}
            for uid, proof in sorted(wave.items()):
                for target, relation, assertion, direction in sorted(adjacency[uid]):
                    if target in seen[seed]:
                        continue
                    seen[seed].add(target)
                    visits += 1
                    if visits > budget:
                        return [], {
                            "status": "incomplete",
                            "reason": "native_frontier_state_bound_exceeded",
                            "visited_states": visits,
                            "frontier_queries": queries,
                        }
                    ids, rels, assertions, directions = proof
                    path = (
                        ids + [target],
                        rels + [relation],
                        assertions + [assertion],
                        directions + [direction],
                    )
                    following[seed][target] = path
                    if target in memory_ids:
                        paths.append(path)
        active = following
    return paths, {
        "status": "ok",
        "visited_states": visits,
        "frontier_queries": queries,
        "max_hops": 4,
        "state_budget": budget,
    }
