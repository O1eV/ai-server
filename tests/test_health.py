from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import APP_VERSION


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": APP_VERSION}


def test_model_status_reports_loaded_bundle(client: TestClient) -> None:
    response = client.get("/api/v1/model/status")
    assert response.status_code == 200
    body = response.json()
    assert body["loaded"] is True
    assert body["device"] == "cpu"
    assert body["model_path"] == "tests/fake-checkpoint"
    assert body["questions"] == ["action"]
    assert body["loaded_at"].startswith("2026-01-01")


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/nope").status_code == 404
