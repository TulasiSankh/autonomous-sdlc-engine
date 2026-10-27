"""Tests for task deletion endpoint, cascading db cleanup, and user file preservation."""

import os
import tempfile
from fastapi.testclient import TestClient

import pytest

from api.main import app
from services.task_service import TaskService
from storage.database import Database


@pytest.fixture
def test_client_and_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path=db_path)

    # Patch environment for Database
    os.environ["SDLC_DB_PATH"] = db_path
    client = TestClient(app)

    yield client, db

    try:
        os.remove(db_path)
    except Exception:
        pass


def test_delete_task_success(test_client_and_db):
    client, db = test_client_and_db

    # Create a task first
    resp = client.post("/tasks", json={"task": "Open my GitHub"})
    assert resp.status_code == 201
    task_data = resp.json()
    task_id = task_data["id"]

    # Verify task exists in list
    list_resp = client.get("/tasks")
    assert any(t["id"] == task_id for t in list_resp.json())

    # Call DELETE endpoint
    del_resp = client.delete(f"/tasks/{task_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Verify task is gone from GET /tasks/{task_id}
    get_resp = client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 404

    # Verify task is gone from list
    list_resp_after = client.get("/tasks")
    assert not any(t["id"] == task_id for t in list_resp_after.json())


def test_delete_task_nonexistent_returns_404(test_client_and_db):
    client, _ = test_client_and_db
    del_resp = client.delete("/tasks/task-nonexistent-12345")
    assert del_resp.status_code == 404
    assert "not found" in del_resp.json()["detail"].lower()


def test_delete_task_does_not_delete_user_files(test_client_and_db):
    client, db = test_client_and_db

    with tempfile.TemporaryDirectory() as user_dir:
        test_file = os.path.join(user_dir, "my_source_code.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Important user work\n")

        # Create task referencing directory
        resp = client.post("/tasks", json={"task": f"Inspect folder {user_dir}"})
        assert resp.status_code == 201
        task_id = resp.json()["id"]

        # Delete the task
        del_resp = client.delete(f"/tasks/{task_id}")
        assert del_resp.status_code == 200

        # Confirm user file and directory are 100% untouched
        assert os.path.exists(user_dir)
        assert os.path.exists(test_file)
        with open(test_file, "r", encoding="utf-8") as f:
            assert f.read() == "# Important user work\n"


def test_delete_actively_executing_task_is_blocked(test_client_and_db):
    client, db = test_client_and_db

    resp = client.post("/tasks", json={"task": "Open my GitHub"})
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # Transition task to in_progress directly in service
    svc = TaskService(db=db)
    svc.transition_task_status(task_id=task_id, new_status="in_progress")

    # Attempt to delete while in_progress
    del_resp = client.delete(f"/tasks/{task_id}")
    assert del_resp.status_code == 400
    assert "actively executing" in del_resp.json()["detail"].lower()
