"""Dense authorized graphs take frontier queries, not exponentially many paths."""

from brain.memory_walk import frontier_paths


class Store:
    def __init__(self, edges):
        self.edges = edges
        self.queries = []

    def memory_query(self, query, params):
        self.queries.append(query)
        return [
            {
                "source": a,
                "target": b,
                "relation": "RELATES_TO",
                "assertion_uid": "",
                "origin": origin,
            }
            for x, y in self.edges
            for a, b, origin in ((x, y, x), (y, x, x))
            if a in params["frontier"] and a in params["allowed"] and b in params["allowed"]
        ]


def test_dense_cycles_return_shortest_paths_with_bounded_queries():
    nodes = {str(n): {} for n in range(30)}
    pairs = [(a, b) for a in nodes for b in nodes if a < b]
    edges = [{"source": a, "target": b, "relation": "RELATES_TO"} for a, b in pairs]
    store = Store(pairs)
    paths, stats = frontier_paths(store, ["0"], nodes, edges, nodes, {"RELATES_TO"})
    assert stats["status"] == "ok" and stats["visited_states"] == 30
    assert len(paths) == 29 and all(len(p[0]) == 2 for p in paths)
    assert len(store.queries) == 2
    assert all("[*" not in query for query in store.queries)


def test_state_budget_and_tampered_edges_fail_closed():
    nodes = {"a": {}, "b": {}}
    edges = [{"source": "a", "target": "b", "relation": "RELATES_TO"}]
    paths, stats = frontier_paths(
        Store([("a", "b")]), ["a"], nodes, edges, nodes, {"RELATES_TO"}, budget=1
    )
    assert paths == [] and stats["status"] == "incomplete"
    paths, stats = frontier_paths(Store([("a", "b")]), ["a"], nodes, [], nodes, {"RELATES_TO"})
    assert paths == [] and stats["reason"] == "retrieval_path_projection_mismatch"
