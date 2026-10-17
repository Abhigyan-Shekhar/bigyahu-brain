"""Physical graph routing checks for synthetic tenants sharing one engine/repo ID."""

import os
import uuid
from dataclasses import replace

import pytest
from test_integration import real as real  # noqa: PLC0414

from brain.graph import GraphStore
from brain.ingest.sync import sync
from brain.services import Services

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("BRAIN_INTEGRATION") != "1", reason="requires FalkorDB"),
]


def test_same_repo_and_principal_stay_isolated_across_tenant_graphs(real):
    assert real.cfg.repo_id.startswith("fixture:")
    tenants = ["fixture_" + uuid.uuid4().hex for _ in range(2)]
    stores = [GraphStore(replace(real.cfg, tenant_id=tenant)) for tenant in tenants]
    try:
        for store in stores:
            sync(store)
        a, b = stores
        uid = real.cfg.repo_id + ":tenant-private-marker"
        a.upsert(
            "Document", uid, {"repo_id": real.cfg.repo_id, "text": "Synthetic confidential marker"}
        )
        a.upsert(
            "Source",
            uid + ":source",
            {
                "repo_id": real.cfg.repo_id,
                "uri": "urn:fixture:tenant-A",
                "excerpt": "Synthetic confidential marker",
            },
        )
        a.edge(uid, "SUPPORTS", uid + ":source")
        assert Services(a).get_context(uid)["items"]
        assert Services(b).get_context(uid)["items"] == []
        for scope in ("org", "private"):
            assert a.cfg.graph_name(scope) != b.cfg.graph_name(scope)
    finally:
        for store in stores:
            if store.db:
                for scope in ("org", "private"):
                    store.db.select_graph(store.cfg.graph_name(scope)).delete()
