"""API smoke tests. Require a populated database (DATABASE_URL); skipped otherwise."""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="needs a database (set DATABASE_URL)"
)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard(client):
    r = client.get("/dashboard/stats")
    assert r.status_code == 200
    body = r.json()
    assert "normalization" in body and "items_total" in body


def test_services_and_partners(client):
    r = client.get("/services", params={"limit": 1})
    assert r.status_code == 200
    r = client.get("/partners", params={"limit": 1})
    assert r.status_code == 200


def test_search(client):
    r = client.get("/search", params={"q": "консультация"})
    assert r.status_code == 200
    assert "services" in r.json() and "partners" in r.json()


def test_unmatched_endpoint(client):
    r = client.get("/unmatched", params={"limit": 5})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
