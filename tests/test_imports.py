import pytest

from brain.ingest.ast_parser import parse
from brain.ingest.imports import resolve_imports


def resolve(text, extra=None):
    texts = {
        "src/pkg/caller.py": text,
        "src/pkg/util.py": "def target(): pass\n",
        "src/pkg/__init__.py": "",
    }
    texts.update(extra or {})
    modules = {p: parse(t, p, "repo", "sha") for p, t in texts.items()}
    resolve_imports(modules, texts)
    return modules["src/pkg/caller.py"]


@pytest.mark.parametrize(
    "statement,call",
    [
        ("import pkg.util", "pkg.util.target"),
        ("import pkg.util as u", "u.target"),
        ("from pkg.util import target", "target"),
        ("from pkg.util import target as t", "t"),
        ("from .util import target", "target"),
        ("from . import util as u", "u.target"),
    ],
)
def test_direct_imports(statement, call):
    module = resolve(f"{statement}\ndef caller():\n    {call}()\n")
    assert module.calls == [
        {
            "source": "repo@sha:src/pkg/caller.py::caller",
            "target": "repo@sha:src/pkg/util.py::target",
            "line": 3,
            "confidence": "static",
            "resolution": "statically_resolved_import",
        }
    ]
    assert not module.unresolved


@pytest.mark.parametrize(
    "text",
    [
        "from .util import target\ndef caller(target):\n    target()\n",
        "from .util import target\ndef caller():\n    target = factory()\n    target()\n",
        "if True:\n    from .util import target\ndef caller():\n    target()\n",
        "from .util import target\ntarget = something\ndef caller():\n    target()\n",
        "from .util import *\ndef caller():\n    target()\n",
        "import pkg.util as u\ndef caller(obj):\n    obj.target()\n",
        "from .util import target\ndef outer(target):\n    def inner():\n        target()\n",
    ],
)
def test_ambiguous_calls_remain_unresolved(text):
    module = resolve(text)
    assert not module.calls
    assert module.unresolved
    assert all(c["resolution"] == "unresolved" for c in module.unresolved)


def test_ambiguous_module_layout():
    assert not resolve(
        "from pkg.util import target\ndef caller(): target()\n",
        {"pkg/util.py": "def target(): pass\n"},
    ).calls


def test_parent_relative_import():
    texts = {
        "src/pkg/sub/caller.py": "from ..util import target\ndef caller(): target()\n",
        "src/pkg/util.py": "def target(): pass\n",
    }
    modules = {p: parse(t, p, "repo", "sha") for p, t in texts.items()}
    resolve_imports(modules, texts)
    assert modules["src/pkg/sub/caller.py"].calls[0]["target"].endswith("util.py::target")


@pytest.mark.parametrize(
    "target", ["if True:\n    def target(): pass\n", "def target(): pass\ntarget = other\n"]
)
def test_rebound_or_conditional_target(target):
    assert not resolve(
        "from .util import target\ndef caller(): target()\n", {"src/pkg/util.py": target}
    ).calls


def test_import_after_call():
    assert not resolve("def caller():\n    target()\n    from .util import target\n").calls
