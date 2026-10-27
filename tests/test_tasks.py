"""Tests for task service and persistent task management API."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from services.task_service import TaskRecord, TaskService
from storage.database import Database


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """Fixture ensuring all tests use a temporary isolated SQLite database."""
    test_db_path = tmp_path / "test_tasks.db"
    monkeypatch.setenv("SDLC_DB_PATH", str(test_db_path))
    db = Database(test_db_path)
    return db


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_task_service_direct_crud(isolated_test_db: Database):
    """Verify TaskService creates, persists, and retrieves tasks directly."""
    service = TaskService(db=isolated_test_db)
    task_desc = "Implement SQLite persistence module"

    # 1. Create task
    record = service.create_task(task_desc)
    assert isinstance(record, TaskRecord)
    assert record.task == task_desc
    assert record.status == "planned"
    assert record.id.startswith("task-")
    assert record.plan.task == task_desc

    # 2. Get task by ID
    fetched = service.get_task(record.id)
    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.task == task_desc
    assert fetched.status == "planned"
    assert fetched.plan.summary == record.plan.summary

    # 3. List tasks
    all_tasks = service.list_tasks()
    assert len(all_tasks) == 1
    assert all_tasks[0].id == record.id

    # 4. Unknown task
    assert service.get_task("nonexistent-id") is None


def test_api_create_task_success(client: TestClient):
    """Verify POST /tasks returns HTTP 201 and persists the task."""
    payload = {"task": "Build persistent task service"}
    response = client.post("/tasks", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["task"] == payload["task"]
    assert data["status"] == "planned"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "plan" in data
    assert data["plan"]["task"] == payload["task"]


def test_api_task_persistence_and_retrieval(client: TestClient):
    """Verify that a task created via POST /tasks can be fetched via GET /tasks/{task_id}."""
    create_response = client.post("/tasks", json={"task": "Implement code review agent"})
    assert create_response.status_code == 201
    task_id = create_response.json()["id"]

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["id"] == task_id
    assert data["task"] == "Implement code review agent"
    assert data["status"] == "planned"
    assert "steps" in data["plan"]


def test_api_list_tasks(client: TestClient):
    """Verify GET /tasks lists all saved tasks."""
    client.post("/tasks", json={"task": "Task Alpha"})
    client.post("/tasks", json={"task": "Task Beta"})

    response = client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    task_names = [t["task"] for t in data]
    assert "Task Alpha" in task_names
    assert "Task Beta" in task_names


def test_api_get_task_unknown_id(client: TestClient):
    """Verify GET /tasks/{task_id} returns HTTP 404 for non-existent IDs."""
    response = client.get("/tasks/non-existent-task-999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "non-existent-task-999" in data["detail"]


def test_api_create_task_empty_input(client: TestClient):
    """Verify POST /tasks rejects empty or whitespace-only task strings."""
    # Empty string
    res_empty = client.post("/tasks", json={"task": ""})
    assert res_empty.status_code == 422

    # Whitespace only
    res_whitespace = client.post("/tasks", json={"task": "   \n\t   "})
    assert res_whitespace.status_code == 422

    # Missing task field
    res_missing = client.post("/tasks", json={})
    assert res_missing.status_code == 422

    # Non-string input
    res_invalid = client.post("/tasks", json={"task": 9999})
    assert res_invalid.status_code == 422
