"""Conservative binding inventory; nested scopes never leak imports into parents."""

import ast
from collections import defaultdict


def bindings(body, package):
    imports, writes = {}, defaultdict(int)

    def scan(node, direct=False):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            writes[node.name] += 1
            # Defaults, decorators and bases execute in the enclosing scope.
            expressions = list(node.decorator_list)
            if isinstance(node, ast.ClassDef):
                expressions += list(node.bases) + [k.value for k in node.keywords]
            else:
                expressions += list(node.args.defaults)
                expressions += [n for n in node.args.kw_defaults if n is not None]
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                args += [a for a in (node.args.vararg, node.args.kwarg) if a]
                expressions += [a.annotation for a in args if a.annotation is not None]
                if node.returns is not None:
                    expressions.append(node.returns)
            for expression in expressions:
                scan(expression)
            return
        if isinstance(node, ast.Lambda):
            for expression in node.args.defaults + node.args.kw_defaults:
                if expression is not None:
                    scan(expression)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                local = alias.asname or (
                    alias.name.split(".")[0] if isinstance(node, ast.Import) else alias.name
                )
                writes[local] += 1
                if not direct or alias.name == "*":
                    continue
                if isinstance(node, ast.Import):
                    imports[local] = (
                        alias.name if alias.asname else alias.name.split(".")[0],
                        alias.name,
                        "module",
                    )
                else:
                    base = node.module or ""
                    if node.level:
                        pieces = package.split(".") if package else []
                        if node.level > len(pieces):
                            continue
                        base = ".".join(
                            pieces[: len(pieces) - node.level + 1] + ([base] if base else [])
                        )
                    full = ".".join(filter(None, [base, alias.name]))
                    imports[local] = (full, full, "from")
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            writes[node.id] += 1
        if isinstance(node, ast.ExceptHandler) and node.name:
            writes[node.name] += 1
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            writes[node.name] += 1
        if isinstance(node, ast.MatchMapping) and node.rest:
            writes[node.rest] += 1
        for child in ast.iter_child_nodes(node):
            scan(child)

    for statement in body:
        scan(statement, direct=True)
    # Any star import can overwrite any otherwise deterministic binding.
    return ({k: v for k, v in imports.items() if writes[k] == 1 and "*" not in writes}, set(writes))
