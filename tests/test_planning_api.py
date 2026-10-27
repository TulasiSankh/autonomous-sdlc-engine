"""Tests for the planning API endpoint POST /tasks/plan."""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_create_plan_valid_task():
    """Verify that POST /tasks/plan returns HTTP 200 and a populated Plan for a valid task."""
    task = "Implement user authentication endpoint"
    response = client.post("/tasks/plan", json={"task": task})

    assert response.status_code == 200
    data = response.json()
    assert data["task"] == task
    assert "authentication endpoint" in data["summary"].lower()
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) > 0
    assert isinstance(data["files_to_inspect"], list)
    assert len(data["files_to_inspect"]) > 0
    assert isinstance(data["acceptance_criteria"], list)
    assert len(data["acceptance_criteria"]) > 0
    assert isinstance(data["tests_to_run"], list)
    assert len(data["tests_to_run"]) > 0
    assert isinstance(data["risks"], list)
    assert len(data["risks"]) > 0


def test_create_plan_response_schema():
    """Verify that POST /tasks/plan response conforms to the Plan schema."""
    task = "Refactor database query performance"
    response = client.post("/tasks/plan", json={"task": task})

    assert response.status_code == 200
    data = response.json()

    expected_keys = {
        "task",
        "summary",
        "steps",
        "files_to_inspect",
        "acceptance_criteria",
        "tests_to_run",
        "risks",
    }
    assert expected_keys.issubset(data.keys())

    # Verify types
    assert isinstance(data["task"], str)
    assert isinstance(data["summary"], str)
    assert all(isinstance(item, str) for item in data["steps"])
    assert all(isinstance(item, str) for item in data["files_to_inspect"])
    assert all(isinstance(item, str) for item in data["acceptance_criteria"])
    assert all(isinstance(item, str) for item in data["tests_to_run"])
    assert all(isinstance(item, str) for item in data["risks"])


def test_create_plan_empty_task():
    """Verify that an empty task string returns HTTP 422."""
    response = client.post("/tasks/plan", json={"task": ""})
    assert response.status_code == 422


def test_create_plan_whitespace_only_task():
    """Verify that a whitespace-only task returns HTTP 422."""
    response = client.post("/tasks/plan", json={"task": "    \n\t   "})
    assert response.status_code == 422


def test_create_plan_missing_task():
    """Verify that a request body missing the task field returns HTTP 422."""
    response = client.post("/tasks/plan", json={})
    assert response.status_code == 422


@pytest.mark.parametrize("invalid_payload", [{"task": None}, {"task": 123}, {"task": []}])
def test_create_plan_invalid_data_types(invalid_payload):
    """Verify that non-string task values return HTTP 422."""
    response = client.post("/tasks/plan", json=invalid_payload)
    assert response.status_code == 422
