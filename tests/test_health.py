from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_check():
    """Verify that GET /health returns HTTP 200 and expected health metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "autonomous-sdlc-engine"
    assert "version" in data
