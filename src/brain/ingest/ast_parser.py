"""Conservative same-module lexical and self.method resolution; no dynamic inference."""

import ast
from dataclasses import dataclass


@dataclass
class Module:
    symbols: list
    calls: list
    unresolved: list


def parse(text, path, repo_id, sha):
    tree = ast.parse(text, filename=path)
    symbols, nodes, parents = [], {}, {}

    def visit(node, prefix="", parent=None):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            qual = f"{prefix}.{node.name}" if prefix else node.name
            uid = f"{repo_id}@{sha}:{path}::{qual}"
            symbols.append(
                {
                    "uid": uid,
                    "path": path,
                    "qualname": qual,
                    "kind": type(node).__name__,
                    "lineno": node.lineno,
                    "end_lineno": node.end_lineno,
                    "revision": sha,
                    "current": True,
                }
            )
            nodes[qual], parents[qual] = node, parent
            for child in ast.iter_child_nodes(node):
                visit(child, qual, qual)
        else:
            for child in ast.iter_child_nodes(node):
                visit(child, prefix, parent)

    visit(tree)
    by_name = {s["qualname"]: s for s in symbols}
    calls, unresolved = [], []
    for qual, node in nodes.items():
        if isinstance(node, ast.ClassDef):
            continue

        # Nested bodies belong to their own symbol, not to the outer function.
        def body_walk(n):
            yield n
            for child in ast.iter_child_nodes(n):
                if not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
                ):
                    yield from body_walk(child)

        bound = {arg.arg for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs}
        bound |= {
            n.id
            for n in body_walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        for n in body_walk(node):
            if not isinstance(n, ast.Call):
                continue
            target, confidence = None, "exact"
            if isinstance(n.func, ast.Name) and n.func.id not in bound:
                prefix = qual.rsplit(".", 1)[0] if "." in qual else ""
                candidates = [f"{prefix}.{n.func.id}" if prefix else n.func.id, n.func.id]
                for candidate in candidates:
                    if candidate in nodes and not isinstance(
                        nodes.get(parents[candidate]), ast.ClassDef
                    ):
                        target = candidate
                        break
            elif isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                parent = parents[qual]
                if n.func.value.id in {"self", "cls"} and isinstance(
                    nodes.get(parent), ast.ClassDef
                ):
                    candidate = f"{parent}.{n.func.attr}"
                    if candidate in nodes:
                        target, confidence = candidate, "heuristic"
            if target:
                calls.append(
                    {
                        "source": by_name[qual]["uid"],
                        "target": by_name[target]["uid"],
                        "confidence": confidence,
                        "line": n.lineno,
                    }
                )
            else:
                unresolved.append(
                    {
                        "caller": by_name[qual]["uid"],
                        "line": n.lineno,
                        "expression": ast.unparse(n.func),
                    }
                )
    return Module(symbols, calls, unresolved)
