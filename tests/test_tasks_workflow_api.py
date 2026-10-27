"""Tests for task workflow API endpoints: POST /tasks/{task_id}/apply and POST /tasks/{task_id}/verify."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from storage.database import Database


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Fixture ensuring all tests use a temporary isolated SQLite database."""
    test_db_path = tmp_path / "test_workflow_api.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(test_db_path))
    monkeypatch.setenv("SDLC_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    return Database(test_db_path)


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_api_apply_proposal_creates_workspace_and_records_diff(client: TestClient):
    """Verify that POST /tasks/{task_id}/apply applies changes, provisions workspace, and returns diffs."""
    # 1. Create a task
    create_res = client.post("/tasks", json={"task": "Implement version endpoint"})
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # 2. Generate proposal
    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 200

    # 3. Apply proposal
    apply_res = client.post(f"/tasks/{task_id}/apply")
    assert apply_res.status_code == 200
    app_data = apply_res.json()

    assert app_data["task_id"] == task_id
    assert app_data["status"] == "applied"
    assert app_data["workspace_id"].startswith("ws_")
    assert len(app_data["changed_files"]) > 0
    assert len(app_data["diffs"]) > 0
    assert "diff" in app_data["diffs"][0]

    # 4. Verify task state has transitioned to 'changes_applied'
    get_res = client.get(f"/tasks/{task_id}")
    assert get_res.status_code == 200
    task_data = get_res.json()
    assert task_data["status"] == "changes_applied"
    assert task_data["workspace_id"] == app_data["workspace_id"]
    assert task_data["application_status"] == "applied"


def test_api_apply_proposal_unknown_task_id(client: TestClient):
    """Verify that applying to a non-existent task returns HTTP 404."""
    res = client.post("/tasks/task-non-existent-999/apply")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_api_apply_proposal_invalid_task_id(client: TestClient):
    """Verify that whitespace task ID returns HTTP 422."""
    res = client.post("/tasks/%20%20%20/apply")
    assert res.status_code == 422


def test_api_verify_task_default_runner_returns_blocked(client: TestClient):
    """Verify that POST /tasks/{task_id}/verify defaults to DisabledSecurityRunner and returns blocked."""
    # 1. Create and apply a task
    create_res = client.post("/tasks", json={"task": "Security verification test"})
    task_id = create_res.json()["id"]
    client.post(f"/tasks/{task_id}/proposal")
    apply_res = client.post(f"/tasks/{task_id}/apply")
    assert apply_res.status_code == 200

    # 2. Run verification
    verif_res = client.post(f"/tasks/{task_id}/verify")
    assert verif_res.status_code == 200
    verif_data = verif_res.json()

    # Truthful reporting: must remain 'blocked', never marked verified without real tests
    assert verif_data["status"] == "blocked"
    assert verif_data["runner_id"] == "disabled-host-protection"
    assert "disabled" in verif_data["error_message"].lower()

    # 3. Check task state transitioned to 'verification_blocked'
    get_res = client.get(f"/tasks/{task_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "verification_blocked"


def test_api_verify_without_workspace_fails(client: TestClient):
    """Verify that calling verify on a task without an applied workspace returns HTTP 400."""
    create_res = client.post("/tasks", json={"task": "Unapplied task"})
    task_id = create_res.json()["id"]

    res = client.post(f"/tasks/{task_id}/verify")
    assert res.status_code == 400
    assert "no associated workspace" in res.json()["detail"].lower()
