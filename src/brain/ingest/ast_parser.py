"""Conservative same-module lexical and self.method resolution; no dynamic inference."""

import ast
from dataclasses import dataclass

from .bindings import bindings


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
    _, module_writes = bindings(tree.body, "")
    stable_definitions = set()
    for definition in tree.body:
        if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        _, other_writes = bindings([d for d in tree.body if d is not definition], "")
        if (
            definition.name not in other_writes
            and "*" not in module_writes
            and not definition.decorator_list
        ):
            stable_definitions.add(definition.name)
    by_name = {s["qualname"]: s for s in symbols}
    calls, unresolved = [], []
    for qual, node in nodes.items():
        if isinstance(node, ast.ClassDef):
            continue

        # Nested bodies belong to their own symbol, not to the outer function.
        def body_walk(n):
            yield n
            children = (
                n.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                else ast.iter_child_nodes(n)
            )
            for child in children:
                if not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
                ):
                    yield from body_walk(child)

        args = node.args.args + node.args.posonlyargs + node.args.kwonlyargs
        args += [a for a in (node.args.vararg, node.args.kwarg) if a]
        _, assigned = bindings(node.body, "")
        bound = set(assigned)
        bound |= {a.arg for a in args}
        unsafe = any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in body_walk(node))
        enclosing = parents[qual]
        while enclosing is not None:
            parent_node = nodes[enclosing]
            if isinstance(parent_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _, outer_bound = bindings(parent_node.body, "")
                outer_args = (
                    parent_node.args.args
                    + parent_node.args.posonlyargs
                    + parent_node.args.kwonlyargs
                )
                outer_args += [a for a in (parent_node.args.vararg, parent_node.args.kwarg) if a]
                bound |= outer_bound | {a.arg for a in outer_args}
                unsafe |= any(
                    isinstance(n, (ast.Global, ast.Nonlocal)) for n in body_walk(parent_node)
                )
            enclosing = parents[enclosing]
        for n in body_walk(node):
            if not isinstance(n, ast.Call):
                continue
            target, confidence = None, "exact"
            if isinstance(n.func, ast.Name) and n.func.id not in bound and not unsafe:
                prefix = qual.rsplit(".", 1)[0] if "." in qual else ""
                candidates = [f"{prefix}.{n.func.id}" if prefix else n.func.id, n.func.id]
                for candidate in candidates:
                    candidate_node = nodes.get(candidate)
                    if (
                        candidate_node is not None
                        and candidate in stable_definitions
                        and not getattr(candidate_node, "decorator_list", [])
                        and not isinstance(nodes.get(parents[candidate]), ast.ClassDef)
                    ):
                        target = candidate
                        break
            elif isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                parent = parents[qual]
                if (
                    n.func.value.id in {"self", "cls"}
                    and n.func.value.id not in assigned
                    and not unsafe
                    and isinstance(nodes.get(parent), ast.ClassDef)
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
