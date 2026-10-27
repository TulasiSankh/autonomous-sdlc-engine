"""Unit tests for newly added specialized agents: ReviewerAgent, TesterAgent, and ArchitectAgent."""

import pytest
from agents.developer import ImplementationProposal, ProposedFileChange, FileDiff
from agents.reviewer import CodeReviewerAgent
from agents.tester import TesterAgent
from agents.architect import ArchitectAgent


def test_reviewer_agent_approved():
    reviewer = CodeReviewerAgent()
    proposal = ImplementationProposal(
        task_id="t-1",
        task="Add harmless helper",
        summary="Add harmless helper",
        files_to_change=[
            ProposedFileChange(path="src/utils.py", action="create", description="Math utility")
        ],
    )
    report = reviewer.review_proposal(
        proposal=proposal,
        file_contents={"src/utils.py": "def add(a: int, b: int) -> int:\n    return a + b\n"}
    )
    assert report.verdict == "approved"
    assert report.auto_approvable is True
    assert report.security_score == 100
    assert len(report.findings) == 0


def test_reviewer_agent_detects_secret():
    reviewer = CodeReviewerAgent()
    proposal = ImplementationProposal(
        task_id="t-2",
        task="Add config with secret",
        summary="Add config with secret",
        files_to_change=[
            ProposedFileChange(path="src/config.py", action="modify", description="Config update")
        ],
    )
    report = reviewer.review_proposal(
        proposal=proposal,
        file_contents={"src/config.py": "API_KEY = 'sk-123456789012345678901234'\n"}
    )
    assert report.verdict == "rejected"
    assert report.auto_approvable is False
    assert any(f.category == "security" and f.severity == "blocker" for f in report.findings)


def test_reviewer_agent_detects_sql_injection():
    reviewer = CodeReviewerAgent()
    proposal = ImplementationProposal(
        task_id="t-3",
        task="User query",
        summary="User query",
        files_to_change=[
            ProposedFileChange(path="src/db.py", action="modify", description="Query")
        ],
    )
    report = reviewer.review_proposal(
        proposal=proposal,
        file_contents={"src/db.py": "query = f'SELECT * FROM users WHERE id = {user_id}'\n"}
    )
    assert report.verdict == "rejected"
    assert any("SQL query injection" in f.message for f in report.findings)


def test_tester_agent_diagnostics_passed():
    tester = TesterAgent()
    diagnosis = tester.diagnose_failure(exit_code=0, stdout="All 10 tests passed", stderr="")
    assert diagnosis.status == "passed"
    assert len(diagnosis.failing_tests) == 0


def test_tester_agent_diagnostics_failed():
    tester = TesterAgent()
    stderr = "FAILED tests/test_login.py::test_auth_failure\nAssertionError: expected 200 got 500"
    diagnosis = tester.diagnose_failure(exit_code=1, stdout="", stderr=stderr)
    assert diagnosis.status == "failed"
    assert "test_auth_failure" in diagnosis.failing_tests or any("AssertionError" in t for t in diagnosis.failing_tests)
    assert "AssertionError" in diagnosis.root_cause_summary or "assertion" in diagnosis.root_cause_summary.lower()


def test_architect_agent_detects_greenfield():
    architect = ArchitectAgent()
    assert architect.detect_greenfield_request("Create a new project for task management") is True
    assert architect.detect_greenfield_request("Build a complete student management system") is True
    assert architect.detect_greenfield_request("Fix bug on line 42") is False


def test_architect_agent_scaffold_fastapi():
    architect = ArchitectAgent()
    proposal = architect.scaffold_project(project_name="my_service", template_type="fastapi_sqlite")
    assert len(proposal.files_to_change) >= 4
    paths = [c.path for c in proposal.files_to_change]
    assert "main.py" in paths
    assert "requirements.txt" in paths
    assert "tests/test_main.py" in paths
