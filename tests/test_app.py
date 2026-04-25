from fastapi.testclient import TestClient

from app import app


def test_health_check():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_renders_index_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Mock Interview Agent" in response.text
