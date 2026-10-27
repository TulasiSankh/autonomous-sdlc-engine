"""QA and Testing Agent module.

Auto-detects test frameworks in the target workspace (pytest, unittest, vitest, jest, cargo, go test),
formulates automated test strategies, evaluates command execution results,
and provides diagnostic guidance to the DeveloperAgent when tests fail.
"""

from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TestFrameworkDetection(BaseModel):
    """Result of inspecting workspace structure for test runners."""

    framework: str = Field(..., description="Detected framework: 'pytest', 'vitest', 'jest', 'go', or 'unknown'.")
    command_profile: str = Field(..., description="Suggested verification profile or command line.")
    config_file: Optional[str] = Field(default=None, description="Configuration file detected (e.g. pytest.ini, vitest.config.ts).")
    test_directory: Optional[str] = Field(default=None, description="Primary test directory located.")


class TestDiagnosis(BaseModel):
    """Structured diagnosis of a failed test run."""

    status: str = Field(..., description="'passed', 'failed', 'blocked', or 'timeout'.")
    failing_tests: List[str] = Field(default_factory=list, description="Names or paths of failing tests.")
    root_cause_summary: str = Field(..., description="Analysis of why the test suite failed.")
    suggested_action: str = Field(..., description="Concrete advice for DeveloperAgent revision.")


class TesterAgent:
    """Agent that handles test framework discovery, execution evaluation, and failure diagnostics."""

    def detect_framework(self, workspace_path: str) -> TestFrameworkDetection:
        """Inspects workspace root and subdirectories to identify available testing harness.

        Args:
            workspace_path: Absolute or relative path to the workspace root.

        Returns:
            TestFrameworkDetection with detected tool and runner profile.
        """
        root = Path(workspace_path)
        if not root.exists():
            return TestFrameworkDetection(
                framework="unknown",
                command_profile="pytest_standard",
                config_file=None,
                test_directory=None,
            )

        # Check Python / Pytest
        if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() or (root / "tests").is_dir():
            test_dir = "tests" if (root / "tests").is_dir() else None
            config = "pytest.ini" if (root / "pytest.ini").exists() else ("pyproject.toml" if (root / "pyproject.toml").exists() else None)
            return TestFrameworkDetection(
                framework="pytest",
                command_profile="pytest_standard",
                config_file=config,
                test_directory=test_dir,
            )

        # Check JS/TS / Vitest / Jest
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                content = pkg_json.read_text(encoding="utf-8")
                if "vitest" in content:
                    return TestFrameworkDetection(
                        framework="vitest",
                        command_profile="npm_test",
                        config_file="package.json",
                        test_directory="src/__tests__",
                    )
                if "jest" in content:
                    return TestFrameworkDetection(
                        framework="jest",
                        command_profile="npm_test",
                        config_file="package.json",
                        test_directory="__tests__",
                    )
            except Exception:
                pass

        # Check Go
        if (root / "go.mod").exists():
            return TestFrameworkDetection(
                framework="go_test",
                command_profile="go_test",
                config_file="go.mod",
                test_directory=None,
            )

        return TestFrameworkDetection(
            framework="pytest",
            command_profile="pytest_standard",
            config_file=None,
            test_directory="tests",
        )

    def diagnose_failure(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> TestDiagnosis:
        """Parses stdout/stderr and exit code to identify failing tests and recommend fixes.

        Args:
            exit_code: Process returncode.
            stdout: Standard output string.
            stderr: Standard error string.

        Returns:
            TestDiagnosis with root cause and suggested remediation.
        """
        combined = f"{stdout}\n{stderr}"
        failing_tests: List[str] = []

        if exit_code == 0:
            return TestDiagnosis(
                status="passed",
                failing_tests=[],
                root_cause_summary="All tests completed successfully.",
                suggested_action="Proceed to task completion verification.",
            )

        # Identify failing test functions in pytest output
        for line in combined.splitlines():
            line_str = line.strip()
            if line_str.startswith("FAILED ") or " FAILED" in line_str:
                parts = line_str.replace("FAILED ", "").split("::")
                failing_tests.append(parts[-1].strip())
            elif "AssertionError:" in line_str:
                failing_tests.append(line_str)

        # Heuristic root cause extraction
        if "ModuleNotFoundError:" in combined or "ImportError:" in combined:
            root_cause = "Missing dependency or unresolved module import in implementation."
            action = "Check requirements.txt or import paths, and ensure package is installed."
        elif "SyntaxError:" in combined:
            root_cause = "Python syntax error or invalid token."
            action = "Fix syntax error before rerunning verification."
        elif "AssertionError:" in combined:
            root_cause = "One or more test assertions failed against expected return values."
            action = "Inspect diff between actual and expected return values in the test suite."
        elif "Timeout" in combined or exit_code == -15:
            root_cause = "Test suite timed out during execution."
            action = "Check for infinite loops, blocking socket calls, or deadlocks."
        else:
            root_cause = f"Test execution failed with non-zero exit code ({exit_code})."
            action = "Review full test error log and patch implementation."

        return TestDiagnosis(
            status="failed",
            failing_tests=failing_tests[:10],
            root_cause_summary=root_cause,
            suggested_action=action,
        )
