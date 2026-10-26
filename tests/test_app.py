from __future__ import annotations

from fastapi.testclient import TestClient


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/nope").status_code == 404
