"""Frozen demo integrity, with no model calls."""

from pathlib import Path

import pytest


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import demo_company_concepts

    return demo_company_concepts


@pytest.mark.parametrize(
    "changed",
    [
        "memory.db",
        "engine/brain.rdb",
        "engine/appendonlydir/base.aof",
        "checkout/policy.md",
        "extra",
    ],
)
def test_prepared_inputs_fail_closed_on_changes(demo, tmp_path, changed):
    for name in (
        "memory.db",
        "engine/brain.rdb",
        "engine/appendonlydir/base.aof",
        "brain.local.yaml",
        "fixture.json",
        "operator-preflight.json",
        "selected-document-concepts.json",
        "checkout/policy.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    before = demo.seal_prepared(tmp_path)
    assert demo.validate_prepared(tmp_path) == before
    target = tmp_path / ("checkout/extra.py" if changed == "extra" else changed)
    target.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="Prepared fixture changed"):
        demo.validate_prepared(tmp_path)
