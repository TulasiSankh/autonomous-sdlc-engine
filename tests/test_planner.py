import pytest
from agents.planner import Plan, PlannerAgent


def test_planner_valid_task():
    """Verify that PlannerAgent returns a valid Plan object for a legitimate task."""
    agent = PlannerAgent()
    task = "Add authentication endpoint to API"
    plan = agent.plan(task)

    assert isinstance(plan, Plan)
    assert plan.task == task
    assert "authentication endpoint" in plan.summary.lower()
    assert len(plan.steps) > 0
    assert len(plan.files_to_inspect) > 0
    assert len(plan.acceptance_criteria) > 0
    assert len(plan.tests_to_run) > 0
    assert len(plan.risks) > 0


def test_planner_structured_output_schema():
    """Verify that Plan produces the required fields and serializes properly."""
    agent = PlannerAgent()
    plan = agent.plan("Refactor database schema")

    dumped = plan.model_dump()
    expected_keys = {
        "task",
        "summary",
        "steps",
        "files_to_inspect",
        "acceptance_criteria",
        "tests_to_run",
        "risks",
    }
    assert expected_keys.issubset(dumped.keys())

    # Check data types
    assert isinstance(dumped["task"], str)
    assert isinstance(dumped["summary"], str)
    assert isinstance(dumped["steps"], list)
    assert isinstance(dumped["files_to_inspect"], list)
    assert isinstance(dumped["acceptance_criteria"], list)
    assert isinstance(dumped["tests_to_run"], list)
    assert isinstance(dumped["risks"], list)

    # Verify JSON export
    json_str = plan.model_dump_json()
    assert "Refactor database schema" in json_str


def test_planner_rejects_empty_task():
    """Verify that an empty string task raises ValueError."""
    agent = PlannerAgent()
    with pytest.raises(ValueError, match="cannot be empty or whitespace only"):
        agent.plan("")


def test_planner_rejects_whitespace_only_task():
    """Verify that a whitespace-only task raises ValueError."""
    agent = PlannerAgent()
    with pytest.raises(ValueError, match="cannot be empty or whitespace only"):
        agent.plan("   \n\t   ")


@pytest.mark.parametrize("invalid_input", [None, 12345, [], {}])
def test_planner_rejects_non_string_task(invalid_input):
    """Verify that non-string task inputs raise ValueError."""
    agent = PlannerAgent()
    with pytest.raises(ValueError, match="Task must be a string"):
        agent.plan(invalid_input)
