"""Resolve direct repository imports only; no runtime dispatch or re-export inference."""

import ast
from collections import defaultdict
from pathlib import PurePosixPath


def resolve_imports(modules, texts):
    names = defaultdict(list)
    module_names = {}
    for path in modules:
        parts = list(PurePosixPath(path).with_suffix("").parts)
        if parts[0] == "src":
            parts.pop(0)
        if parts[-1] == "__init__":
            parts.pop()
        name = ".".join(parts)
        names[name].append(path)
        module_names[path] = name
    unique = {name: paths[0] for name, paths in names.items() if len(paths) == 1}

    def bindings(body, package):
        imports, writes = {}, defaultdict(int)
        for statement in body:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    if alias.name == "*":
                        return {}, {"*"}
                    local = alias.asname or (
                        alias.name.split(".")[0]
                        if isinstance(statement, ast.Import)
                        else alias.name
                    )
                    writes[local] += 1
                    if isinstance(statement, ast.Import):
                        imports[local] = (
                            alias.name if alias.asname else alias.name.split(".")[0],
                            alias.name,
                            "module",
                        )
                    else:
                        base = statement.module or ""
                        if statement.level:
                            pieces = package.split(".") if package else []
                            if statement.level > len(pieces):
                                continue
                            base = ".".join(
                                pieces[: len(pieces) - statement.level + 1]
                                + ([base] if base else [])
                            )
                        full = ".".join(filter(None, [base, alias.name]))
                        imports[local] = (full, full, "from")
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                writes[statement.name] += 1
            else:
                # Conditional imports, assignments, deletions and loop bindings are ambiguous.
                for node in ast.walk(statement):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                        writes[node.id] += 1
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        for alias in node.names:
                            writes[alias.asname or alias.name.split(".")[0]] += 1
        return {k: v for k, v in imports.items() if writes[k] == 1}, set(writes)

    functions = {}
    for path, module in modules.items():
        tree = ast.parse(texts[path], filename=path)
        definitions = {
            n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # A definition must be unique and not rebound elsewhere at module level.
        for symbol in module.symbols:
            name = symbol["qualname"]
            node = definitions.get(name)
            if node is None:
                continue
            other = [n for n in tree.body if n is not node]
            _, writes = bindings(other, "")
            if name not in writes and "*" not in writes:
                functions[(module_names[path], name)] = symbol["uid"]

    for path, module in modules.items():
        tree = ast.parse(texts[path], filename=path)
        name = module_names[path]
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        imported, _ = bindings(tree.body, package)
        scopes = {}
        local_lines = {}

        def visit(
            body,
            prefix="",
            nested=False,
            package=package,
            imported=imported,
            scopes=scopes,
            local_lines=local_lines,
        ):
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qual = ".".join(filter(None, [prefix, node.name]))
                    if not isinstance(node, ast.ClassDef):
                        local, writes = bindings(node.body, package)
                        args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                        blocked = writes | {a.arg for a in args}
                        blocked |= {a.arg for a in [node.args.vararg, node.args.kwarg] if a}
                        # Closures and global/nonlocal mutation need a more complete scope analysis.
                        unsafe = nested or any(
                            isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(node)
                        )
                        environment = (
                            {}
                            if unsafe or "*" in writes
                            else {k: v for k, v in imported.items() if k not in blocked}
                        )
                        if not unsafe:
                            environment.update(
                                {k: v for k, v in local.items() if k not in {a.arg for a in args}}
                            )
                        scopes[qual] = environment
                        local_lines[qual] = {
                            alias.asname
                            or (
                                alias.name.split(".")[0]
                                if isinstance(n, ast.Import)
                                else alias.name
                            ): n.lineno
                            for n in node.body
                            if isinstance(n, (ast.Import, ast.ImportFrom))
                            for alias in n.names
                        }
                    visit(node.body, qual, nested or not isinstance(node, ast.ClassDef))

        visit(tree.body)
        remaining = []
        for call in module.unresolved:
            expression = call["expression"].split(".")
            qual = call["caller"].split("::", 1)[1]
            target = scopes.get(qual, {}).get(expression[0])
            if local_lines.get(qual, {}).get(expression[0], 0) >= call["line"]:
                target = None
            dotted = ".".join([target[0], *expression[1:]]) if target else ""
            target_module, _, target_name = dotted.rpartition(".")
            eligible = target and (
                target_module == target[1] or (target[2] == "from" and dotted == target[1])
            )
            uid = (
                functions.get((target_module, target_name))
                if eligible and target_module in unique
                else None
            )
            if uid:
                module.calls.append(
                    {
                        "source": call["caller"],
                        "target": uid,
                        "line": call["line"],
                        "confidence": "static",
                        "resolution": "statically_resolved_import",
                    }
                )
            else:
                remaining.append({**call, "resolution": "unresolved"})
        module.unresolved = remaining
