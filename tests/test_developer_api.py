"""Tests for the Developer Agent proposal API endpoint POST /tasks/{task_id}/proposal."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from storage.database import Database


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Fixture ensuring all tests use a temporary isolated SQLite database."""
    test_db_path = tmp_path / "test_developer_api.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(test_db_path))
    return Database(test_db_path)


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_api_create_proposal_valid_task(client: TestClient):
    """Verify that POST /tasks/{task_id}/proposal returns HTTP 200 and a valid ImplementationProposal."""
    task_desc = "Implement OAuth2 login endpoint"
    create_res = client.post("/tasks", json={"task": task_desc})
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    proposal_res = client.post(f"/tasks/{task_id}/proposal")
    assert proposal_res.status_code == 200

    data = proposal_res.json()
    assert data["task_id"] == task_id
    assert data["task"] == task_desc
    assert data["status"] == "proposed"
    assert data["dry_run"] is True
    assert "oauth2" in data["summary"].lower() or "login" in data["summary"].lower()

    # Verify file change items
    assert isinstance(data["files_to_change"], list)
    assert len(data["files_to_change"]) > 0
    for change in data["files_to_change"]:
        assert "path" in change
        assert change["action"] in ("create", "modify")
        assert "description" in change

    # Verify execution steps and verification commands
    assert isinstance(data["execution_steps"], list)
    assert len(data["execution_steps"]) > 0
    assert isinstance(data["verification_commands"], list)
    assert len(data["verification_commands"]) > 0


def test_api_create_proposal_unknown_task_id(client: TestClient):
    """Verify that POST /tasks/{task_id}/proposal returns HTTP 404 for non-existent task IDs."""
    response = client.post("/tasks/task-non-existent-777/proposal")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "task-non-existent-777" in data["detail"]


def test_api_create_proposal_invalid_task_id(client: TestClient):
    """Verify that whitespace-only task IDs return HTTP 422."""
    response = client.post("/tasks/%20%20%20/proposal")
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_api_create_proposal_response_schema(client: TestClient):
    """Verify that the proposal response payload matches the complete ImplementationProposal schema."""
    create_res = client.post("/tasks", json={"task": "Add rate limiter middleware"})
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    proposal_res = client.post(f"/tasks/{task_id}/proposal")
    assert proposal_res.status_code == 200
    data = proposal_res.json()

    expected_keys = {
        "task_id",
        "task",
        "status",
        "summary",
        "files_to_change",
        "execution_steps",
        "verification_commands",
        "dry_run",
    }
    assert expected_keys.issubset(data.keys())

    # Verify types
    assert isinstance(data["task_id"], str)
    assert isinstance(data["task"], str)
    assert isinstance(data["status"], str)
    assert isinstance(data["summary"], str)
    assert isinstance(data["files_to_change"], list)
    assert isinstance(data["execution_steps"], list)
    assert isinstance(data["verification_commands"], list)
    assert isinstance(data["dry_run"], bool)


def test_api_create_proposal_dry_run_leaves_workspace_unchanged(client: TestClient, tmp_path: Path):
    """Verify that calling the proposal API endpoint creates or modifies zero files on disk."""
    create_res = client.post("/tasks", json={"task": "Dry run verification test"})
    task_id = create_res.json()["id"]

    # Record workspace state before API invocation (excluding sqlite database files)
    before_state = {
        p: p.stat().st_mtime
        for p in tmp_path.rglob("*")
        if not p.name.endswith((".db", ".db-journal", ".db-wal", ".db-shm"))
    }

    res = client.post(f"/tasks/{task_id}/proposal")
    assert res.status_code == 200
    assert res.json()["dry_run"] is True

    # Record workspace state after API invocation
    after_state = {
        p: p.stat().st_mtime
        for p in tmp_path.rglob("*")
        if not p.name.endswith((".db", ".db-journal", ".db-wal", ".db-shm"))
    }

    # Assert no code files inside the temporary test sandbox were created or modified
    assert before_state == after_state


def test_api_proposal_persistence_and_lifecycle_update(client: TestClient):
    """Verify that generating a proposal persists the proposal and updates task lifecycle to proposed."""
    task_desc = "Add structured JSON logging middleware"
    create_res = client.post("/tasks", json={"task": task_desc})
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # Before proposal: task status is planned, proposal is None
    get_before = client.get(f"/tasks/{task_id}").json()
    assert get_before["status"] == "planned"
    assert get_before["proposal"] is None

    # Generate proposal
    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 200
    prop_data = prop_res.json()
    assert prop_data["status"] == "proposed"
    assert "diffs" in prop_data
    assert len(prop_data["diffs"]) > 0

    # After proposal: task is persisted in SQLite with status 'proposed' and proposal attached
    get_after = client.get(f"/tasks/{task_id}").json()
    assert get_after["status"] == "proposed"
    assert get_after["proposal"] is not None
    assert get_after["proposal"]["task_id"] == task_id
    assert len(get_after["proposal"]["diffs"]) > 0

    # Task list also reflects the persisted proposal
    tasks_list = client.get("/tasks").json()
    matching = [t for t in tasks_list if t["id"] == task_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "proposed"
    assert matching[0]["proposal"] is not None


def test_api_proposal_diffs_content_and_headers(client: TestClient):
    """Verify that generated candidate diffs contain valid file headers and unified diff formatting."""
    create_res = client.post("/tasks", json={"task": "Implement API rate limiting"})
    task_id = create_res.json()["id"]

    prop_res = client.post(f"/tasks/{task_id}/proposal")
    assert prop_res.status_code == 200
    data = prop_res.json()

    diffs = data.get("diffs", [])
    assert len(diffs) > 0
    for diff_entry in diffs:
        assert "path" in diff_entry
        assert diff_entry["change_type"] in ("added", "modified")
        diff_text = diff_entry["diff"]
        assert "@@" in diff_text
        if diff_entry["change_type"] == "added":
            assert "--- /dev/null" in diff_text
            assert f"+++ b/{diff_entry['path']}" in diff_text
        else:
            assert f"--- a/{diff_entry['path']}" in diff_text
            assert f"+++ b/{diff_entry['path']}" in diff_text


def test_api_proposal_generation_failure_on_corrupted_plan(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Verify that a task with empty execution steps raises HTTP 422 with useful detail."""
    create_res = client.post("/tasks", json={"task": "Corrupted plan test task"})
    task_id = create_res.json()["id"]

    # Mock TaskService to return a task with empty steps
    from services.task_service import TaskService
    original_get = TaskService.get_task

    def mock_get(self, tid):
        rec = original_get(self, tid)
        if rec and rec.id == task_id:
            rec.plan.steps = []
        return rec

    monkeypatch.setattr(TaskService, "get_task", mock_get)

    res = client.post(f"/tasks/{task_id}/proposal")
    assert res.status_code == 422
    assert "no execution steps" in res.json()["detail"].lower()


def test_api_proposal_regeneration_on_already_proposed_task(client: TestClient):
    """Verify that re-generating a proposal on an already proposed task is allowed and idempotent."""
    create_res = client.post("/tasks", json={"task": "Re-proposal idempotency test"})
    task_id = create_res.json()["id"]

    res1 = client.post(f"/tasks/{task_id}/proposal")
    assert res1.status_code == 200
    assert res1.json()["status"] == "proposed"

    res2 = client.post(f"/tasks/{task_id}/proposal")
    assert res2.status_code == 200
    assert res2.json()["status"] == "proposed"
    assert res2.json()["task_id"] == task_id

