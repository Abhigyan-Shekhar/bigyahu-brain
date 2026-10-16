"""Binding regressions shared by lexical and imported call resolution."""

import pytest

from brain.ingest.ast_parser import parse
from brain.ingest.imports import resolve_imports


@pytest.mark.parametrize(
    "binding",
    [
        "if flag:\n    def target(): pass",
        "try:\n    pass\nexcept Exception as target:\n    pass",
        'match value:\n    case {"x": target}: pass',
        "del target",
        "target = other",
    ],
)
def test_module_shadowing_blocks_lexical_and_imported_calls(binding):
    for definition in ("def target(): pass", "from util import target"):
        texts = {
            "caller.py": f"{definition}\n{binding}\ndef caller(): target()\n",
            "util.py": "def target(): pass\n",
        }
        modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
        resolve_imports(modules, texts)
        assert not modules["caller.py"].calls
        assert modules["caller.py"].unresolved


@pytest.mark.parametrize("args", ["*target", "**target"])
def test_variadic_argument_shadows_local_import(args):
    texts = {
        "caller.py": f"def caller({args}):\n    from util import target\n    target()\n",
        "util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_nested_import_does_not_shadow_parent_binding():
    texts = {
        "caller.py": "from util import target\ndef caller():\n"
        "    def inner():\n        from other import target\n    target()\n",
        "util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert len(modules["caller.py"].calls) == 1
    assert modules["caller.py"].calls[0]["target"].endswith("util.py::target")


def test_closure_shadowing_prevents_false_global_edge():
    module = parse(
        "def target(): pass\ndef outer(target):\n    def inner(): target()\n", "x.py", "r", "s"
    )
    assert not module.calls


def test_ambiguous_parent_package():
    texts = {
        "caller.py": "from pkg.util import target\ndef caller(): target()\n",
        "pkg.py": "",
        "pkg/__init__.py": "",
        "pkg/util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_rebound_self_is_unresolved():
    module = parse(
        "class C:\n    def a(self): pass\n"
        "    def b(self):\n        self = other\n        self.a()\n",
        "x.py",
        "r",
        "s",
    )
    assert not module.calls


@pytest.mark.parametrize(
    "export",
    [
        "from .util import target",
        "from .middle import target",
    ],
)
def test_explicit_reexport_chain(export):
    texts = {
        "caller.py": "from pkg import target\ndef caller(): target()\n",
        "pkg/__init__.py": export,
        "pkg/middle.py": "from .util import target",
        "pkg/util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert modules["caller.py"].calls[0]["target"].endswith("pkg/util.py::target")


@pytest.mark.parametrize(
    "export",
    [
        "from .util import target\ntarget = replacement",
        "if flag:\n    from .util import target",
        "from .middle import target",
        "from .util import *",
    ],
)
def test_ambiguous_or_cyclic_reexport(export):
    texts = {
        "caller.py": "from pkg import target\ndef caller(): target()\n",
        "pkg/__init__.py": export,
        "pkg/middle.py": "from . import target",
        "pkg/util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_module_file_shadows_namespace_package():
    texts = {
        "caller.py": "from pkg.util import target\ndef caller(): target()\n",
        "pkg.py": "",
        "pkg/util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_default_calls_are_not_function_body_calls():
    module = parse("def target(): pass\ndef caller(value=target()): pass\n", "x.py", "r", "s")
    assert not module.calls


@pytest.mark.parametrize(
    "statement",
    [
        "def other(value=(target := replacement)): pass",
        "@(target := replacement)\ndef other(): pass",
        "class Other((target := replacement)): pass",
    ],
)
def test_definition_expressions_can_shadow_imports(statement):
    texts = {
        "caller.py": f"from util import target\n{statement}\ndef caller(): target()\n",
        "util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_decorated_target_is_not_exactly_resolved():
    texts = {
        "caller.py": "from util import target\ndef caller(): target()\n",
        "util.py": "@decorator\ndef target(): pass\n",
    }
    modules = {p: parse(t, p, "r", "s") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert not modules["caller.py"].calls


def test_unshadowed_same_module_constructor_remains_resolved():
    module = parse("class Target: pass\ndef caller(): return Target()\n", "x.py", "r", "s")
    assert module.calls[0]["target"] == "r@s:x.py::Target"
