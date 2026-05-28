"""RRM-3 API smoke tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.rrm3
def test_adaptive_policy_endpoint_shape(client):
    from core.config import settings

    r = client.get("/api/v1/sessions/test-s/adaptive-policy")
    if settings.auth_disabled:
        assert r.status_code == 200
    else:
        assert r.status_code in (401, 403)


@pytest.mark.rrm3
def test_tools_reliability_endpoint_shape(client):
    from core.config import settings

    r = client.get("/api/v1/tools/reliability")
    if settings.auth_disabled:
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    else:
        assert r.status_code in (401, 403)
