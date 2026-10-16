"""Resolve deterministic imports and explicit re-exports; no runtime dispatch."""

import ast
from collections import defaultdict
from pathlib import PurePosixPath

from .bindings import bindings


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

    def unambiguous(name):
        return name in unique and all(
            len(names[".".join(name.split(".")[:i])]) <= 1
            and (
                i == len(name.split("."))
                or all(p.endswith("/__init__.py") for p in names[".".join(name.split(".")[:i])])
            )
            for i in range(1, len(name.split(".")) + 1)
        )

    exports = {}
    for path in modules:
        name = module_names[path]
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        exports[name], _ = bindings(ast.parse(texts[path]).body, package)

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
            if node is None or node.decorator_list:
                continue
            other = [n for n in tree.body if n is not node]
            _, writes = bindings(other, "")
            if name not in writes and "*" not in writes:
                functions[(module_names[path], name)] = symbol["uid"]

    def exported_function(module_name, symbol_name, seen=None):
        key = (module_name, symbol_name)
        seen = set() if seen is None else seen
        if key in seen or not unambiguous(module_name):
            return None
        if key in functions:
            return functions[key]
        seen.add(key)
        binding = exports.get(module_name, {}).get(symbol_name)
        # Only explicit from-import aliases re-export a function. No star imports,
        # module __getattr__, assignment aliases, or conditional fallback imports.
        if binding and binding[2] == "from":
            next_module, _, next_symbol = binding[0].rpartition(".")
            return exported_function(next_module, next_symbol, seen)
        return None

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
                        args += [a for a in (node.args.vararg, node.args.kwarg) if a]
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
            uid = exported_function(target_module, target_name) if eligible else None
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
