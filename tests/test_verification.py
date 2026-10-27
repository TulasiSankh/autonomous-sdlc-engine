"""Comprehensive tests for verification service, policy validation, and runner contracts."""

from pathlib import Path
import subprocess
import pytest

from services.verification_service import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DisabledSecurityRunner,
    SubprocessSandboxRunner,
    VerificationRequest,
    VerificationResult,
    VerificationService,
    sanitize_environment,
)
from services.workspace_service import WorkspaceService


@pytest.fixture
def workspace_service(tmp_path: Path) -> WorkspaceService:
    """Fixture providing WorkspaceService in a temp directory."""
    ws_root = tmp_path / "verification_workspaces"
    return WorkspaceService(workspace_root=ws_root, default_source_repo=tmp_path)


def test_verification_result_schema_validation():
    """Verify that VerificationResult schema validates all required fields and serializes to JSON."""
    result = VerificationResult(
        workspace_id="ws_test123",
        profile="pytest_standard",
        status="passed",
        exit_code=0,
        duration_seconds=1.23,
        stdout="collected 1 item\ntest passed",
        stderr="",
        output_truncated=False,
        timed_out=False,
        runner_id="test-runner",
        timestamp="2026-10-13T12:00:00Z",
        error_message=None,
    )

    dumped = result.model_dump()
    assert dumped["status"] == "passed"
    assert dumped["exit_code"] == 0
    assert dumped["timed_out"] is False

    json_str = result.model_dump_json()
    assert "ws_test123" in json_str
    assert "pytest_standard" in json_str


def test_disabled_security_runner_default_behavior(workspace_service: WorkspaceService):
    """Verify that by default, execution is blocked with an informative security message."""
    ws_info = workspace_service.create_workspace()
    # Add tests directory so pre-validation passes
    ws_path = Path(ws_info.workspace_path)
    (ws_path / "tests").mkdir()
    (ws_path / "tests" / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    service = VerificationService(workspace_service=workspace_service)
    assert isinstance(service.runner, DisabledSecurityRunner)

    req = VerificationRequest(workspace_id=ws_info.workspace_id, profile="pytest_standard")
    result = service.verify_workspace(req)

    assert result.status == "blocked"
    assert result.exit_code is None
    assert result.duration_seconds == 0.0
    assert result.runner_id == "disabled-host-protection"
    assert "Execution blocked: Secure container isolation" in result.error_message


def test_invalid_and_untracked_workspace_id_rejected(workspace_service: WorkspaceService):
    """Verify that unverified or non-existent workspace IDs return error status."""
    service = VerificationService(workspace_service=workspace_service)
    req = VerificationRequest(workspace_id="ws_non_existent_999", profile="pytest_standard")
    result = service.verify_workspace(req)

    assert result.status == "error"
    assert "Workspace verification failed" in result.error_message


def test_unsupported_verification_profile_rejected(workspace_service: WorkspaceService):
    """Verify that profiles outside the strict allowlist raise ValueError."""
    ws_info = workspace_service.create_workspace()
    service = VerificationService(workspace_service=workspace_service)

    with pytest.raises(ValueError):
        VerificationRequest(
            workspace_id=ws_info.workspace_id,
            profile="arbitrary_bash_command",  # type: ignore[arg-type]
        )


def test_missing_test_files_rejected(workspace_service: WorkspaceService):
    """Verify that workspaces without tests/ or test files fail validation before execution."""
    ws_info = workspace_service.create_workspace()
    service = VerificationService(workspace_service=workspace_service)

    # 1. No tests/ directory
    req = VerificationRequest(workspace_id=ws_info.workspace_id, profile="pytest_standard")
    res1 = service.verify_workspace(req)
    assert res1.status == "error"
    assert "does not contain a 'tests/' directory" in res1.error_message

    # 2. Empty tests/ directory
    ws_path = Path(ws_info.workspace_path)
    (ws_path / "tests").mkdir()
    res2 = service.verify_workspace(req)
    assert res2.status == "error"
    assert "No test files" in res2.error_message


def test_sanitize_environment():
    """Verify that sanitize_environment strips API keys, tokens, and credentials."""
    dirty_env = {
        "PATH": "C:/Windows/System32",
        "SYSTEMROOT": "C:/Windows",
        "OPENAI_API_KEY": "sk-secret123",
        "ANTHROPIC_API_KEY": "ant-secret456",
        "GITHUB_TOKEN": "ghp_token789",
        "AWS_SECRET_ACCESS_KEY": "aws-secret",
        "SDLC_DB_PATH": "data/tasks.db",
        "MY_DATABASE_PASSWORD": "password123",
        "USER_AUTH_TOKEN": "token_abc",
    }

    clean_env = sanitize_environment(dirty_env)
    assert "PATH" in clean_env
    assert "SYSTEMROOT" in clean_env
    assert "PYTHONUNBUFFERED" in clean_env
    assert "PYTHONDONTWRITEBYTECODE" in clean_env

    # Secrets stripped
    assert "OPENAI_API_KEY" not in clean_env
    assert "ANTHROPIC_API_KEY" not in clean_env
    assert "GITHUB_TOKEN" not in clean_env
    assert "AWS_SECRET_ACCESS_KEY" not in clean_env
    assert "SDLC_DB_PATH" not in clean_env
    assert "MY_DATABASE_PASSWORD" not in clean_env
    assert "USER_AUTH_TOKEN" not in clean_env


def test_subprocess_runner_successful_execution(workspace_service: WorkspaceService):
    """Verify that SubprocessSandboxRunner executes tests and accurately captures success."""
    ws_info = workspace_service.create_workspace()
    ws_path = Path(ws_info.workspace_path)
    (ws_path / "tests").mkdir()
    (ws_path / "tests" / "test_math.py").write_text(
        "def test_addition():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )

    runner = SubprocessSandboxRunner(allow_host_execution=True)
    service = VerificationService(workspace_service=workspace_service, runner=runner)

    req = VerificationRequest(workspace_id=ws_info.workspace_id, profile="pytest_fast")
    result = service.verify_workspace(req)

    assert result.status == "passed"
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.duration_seconds > 0.0
    assert "passed" in result.stdout.lower() or "1 passed" in result.stdout


def test_subprocess_runner_failing_tests(workspace_service: WorkspaceService):
    """Verify that SubprocessSandboxRunner accurately captures test failures and exit code."""
    ws_info = workspace_service.create_workspace()
    ws_path = Path(ws_info.workspace_path)
    (ws_path / "tests").mkdir()
    (ws_path / "tests" / "test_fail.py").write_text(
        "def test_failure():\n    assert 1 == 999\n", encoding="utf-8"
    )

    runner = SubprocessSandboxRunner(allow_host_execution=True)
    service = VerificationService(workspace_service=workspace_service, runner=runner)

    req = VerificationRequest(workspace_id=ws_info.workspace_id, profile="pytest_fast")
    result = service.verify_workspace(req)

    assert result.status == "failed"
    assert result.exit_code != 0
    assert result.timed_out is False
    assert "failed" in result.stdout.lower() or "assert 1 == 999" in result.stdout


def test_subprocess_runner_timeout_handling(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Verify that timeout expiration is handled cleanly and marked as timed_out."""
    runner = SubprocessSandboxRunner(allow_host_execution=True)

    def mock_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=5.0, output="partial output")

    monkeypatch.setattr(subprocess, "run", mock_run)

    dummy_path = tmp_path / "ws_dummy"
    dummy_path.mkdir()

    result = runner.run(
        workspace_path=dummy_path,
        command_args=["python", "-m", "pytest"],
        timeout_seconds=5.0,
    )

    assert result.status == "timed_out"
    assert result.timed_out is True
    assert result.exit_code is None
    assert "timed out after 5.0 seconds" in result.error_message


def test_subprocess_runner_output_truncation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Verify that large output streams are truncated to avoid memory bloat."""
    runner = SubprocessSandboxRunner(allow_host_execution=True)

    huge_output = "A" * 100000

    class MockCompletedProcess:
        returncode = 0
        stdout = huge_output
        stderr = "short stderr"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockCompletedProcess())

    dummy_path = tmp_path / "ws_dummy"
    dummy_path.mkdir()

    result = runner.run(
        workspace_path=dummy_path,
        command_args=["python", "-m", "pytest"],
        timeout_seconds=30.0,
        max_output_bytes=1000,
    )

    assert result.output_truncated is True
    assert "[STDOUT TRUNCATED]" in result.stdout
    assert len(result.stdout) < len(huge_output)


def test_subprocess_runner_launch_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Verify that process launch errors (e.g. executable not found) return error status."""
    runner = SubprocessSandboxRunner(allow_host_execution=True)

    def mock_fail(*args, **kwargs):
        raise FileNotFoundError("Executable not found")

    monkeypatch.setattr(subprocess, "run", mock_fail)

    dummy_path = tmp_path / "ws_dummy"
    dummy_path.mkdir()

    result = runner.run(
        workspace_path=dummy_path,
        command_args=["nonexistent_exec"],
        timeout_seconds=10.0,
    )

    assert result.status == "error"
    assert "Failed to launch verification runner" in result.error_message
