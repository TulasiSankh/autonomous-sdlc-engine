"""Planner Agent module.

Provides deterministic task intent classification and structured plan generation
for both autonomous software engineering workflows and real local computer tasks.
"""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agents.intent_classifier import KNOWN_APPS, TaskIntent, TaskIntentClassifier
from local_agent.system_inspector import SystemInspector


class ToolStep(BaseModel):
    """Actionable tool step for computer task execution."""

    step_number: int = Field(..., description="1-indexed sequence number of the step.")
    description: str = Field(..., description="Human-readable description of what this step does.")
    tool: str = Field(..., description="Target tool: browser, filesystem, app_launcher, command, verification.")
    action: str = Field(..., description="Target action to execute on the tool.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Validated parameters for the tool action.")
    expected_outcome: str = Field(..., description="Measurable expected outcome of this step.")
    requires_approval: bool = Field(default=False, description="Whether this step requires explicit user confirmation.")


class Plan(BaseModel):
    """Structured execution plan for SDLC and computer tasks."""

    task: str = Field(..., description="The raw input task description.")
    summary: str = Field(..., description="High-level summary of the execution strategy.")
    task_type: str = Field(
        default="code_change",
        description="Intent category: application_action, browser_action, filesystem_action, command_action, composite_action, code_change, unsupported.",
    )
    steps: List[str] = Field(default_factory=list, description="Actionable sequential steps to execute.")
    tool_steps: List[ToolStep] = Field(default_factory=list, description="Machine-executable tool steps.")
    files_to_inspect: List[str] = Field(
        default_factory=list, description="Candidate files and directories to inspect."
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list, description="Measurable criteria defining task completion."
    )
    tests_to_run: List[str] = Field(
        default_factory=list, description="Test commands or suites to verify changes."
    )
    risks: List[str] = Field(
        default_factory=list, description="Identified technical risks and potential regressions."
    )
    target_path: Optional[str] = Field(default=None, description="Primary filesystem target path if applicable.")
    target_url: Optional[str] = Field(default=None, description="Primary URL target if applicable.")
    target_app: Optional[str] = Field(default=None, description="Primary application target if applicable.")


class PlannerAgent:
    """Agent responsible for classifying task intents and generating tailored execution plans."""

    def __init__(self, name: str = "PlannerAgent") -> None:
        self.name: str = name

    def validate_task(self, task: str) -> str:
        """Validates that the task is a non-empty string.

        Args:
            task: Task description string.

        Returns:
            The sanitized task string stripped of leading/trailing whitespace.

        Raises:
            ValueError: If task is empty, contains only whitespace, or is not a string.
        """
        if not isinstance(task, str):
            raise ValueError("Task must be a string.")

        cleaned = task.strip()
        if not cleaned:
            raise ValueError("Task description cannot be empty or whitespace only.")

        return cleaned

    def plan(self, task: str) -> Plan:
        """Classifies task intent and generates a structured, specific execution plan.

        Args:
            task: Raw task description.

        Returns:
            A populated Plan model specific to the classified intent.

        Raises:
            ValueError: If task validation fails.
        """
        clean_task = self.validate_task(task)
        intent: TaskIntent = TaskIntentClassifier.classify(clean_task)

        if intent == "application_action":
            return self._plan_application_action(clean_task)
        elif intent == "browser_action":
            return self._plan_browser_action(clean_task)
        elif intent == "filesystem_action":
            return self._plan_filesystem_action(clean_task)
        elif intent == "composite_action":
            return self._plan_composite_action(clean_task)
        elif intent == "command_action":
            return self._plan_command_action(clean_task)
        elif intent == "unsupported":
            return self._plan_unsupported(clean_task)
        else:
            return self._plan_code_change(clean_task)

    def _plan_application_action(self, clean_task: str) -> Plan:
        """Generates a plan for launching an installed desktop application."""
        target_app = self._extract_app_name(clean_task)
        target_path = self._extract_target_path(clean_task)

        steps = [
            f"1. Detect the operating system and locate {target_app} executable.",
            f"2. Launch {target_app}." if not target_path else f"2. Launch {target_app} with '{target_path}'.",
            f"3. Confirm that the launch action succeeded.",
            f"4. Persist the result and update the task status.",
        ]

        launch_params: Dict[str, Any] = {"app_name": target_app}
        if target_path:
            launch_params["target_path"] = target_path

        tool_steps = [
            ToolStep(
                step_number=1,
                description=f"Detect whether '{target_app}' is installed and locate its executable.",
                tool="app_launcher",
                action="detect",
                parameters={"app_name": target_app},
                expected_outcome=f"Executable path for '{target_app}' discovered on host system.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=2,
                description=f"Launch application '{target_app}'" + (f" with target path '{target_path}'" if target_path else "."),
                tool="app_launcher",
                action="launch",
                parameters=launch_params,
                expected_outcome=f"Application '{target_app}' launched safely without shell=True.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=3,
                description=f"Confirm that application '{target_app}' process was created.",
                tool="verification",
                action="verify_process_running",
                parameters={"target": target_app, "app_name": target_app},
                expected_outcome=f"Process launch for '{target_app}' confirmed by operating system.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=4,
                description=f"Verify that a visible window for '{target_app}' appears on user desktop.",
                tool="verification",
                action="verify_visible_window",
                parameters={"target": target_app, "app_name": target_app, "timeout": 3.0},
                expected_outcome=f"Top-level window for '{target_app}' verified visible on interactive desktop.",
                requires_approval=False,
            ),
        ]

        return Plan(
            task=clean_task,
            summary=f"Deterministic plan for application task: '{clean_task}'.",
            task_type="application_action",
            steps=[
                f"1. Detect the operating system and locate {target_app} executable.",
                f"2. Launch {target_app}." if not target_path else f"2. Launch {target_app} with '{target_path}'.",
                f"3. Confirm that the application process started.",
                f"4. Verify that a visible application window is open on the user desktop.",
                f"5. Persist the result and update the task status.",
            ],
            tool_steps=tool_steps,
            target_app=target_app,
            target_path=target_path,
            files_to_inspect=[],
            acceptance_criteria=[
                f"Application '{target_app}' located on host system.",
                f"Application '{target_app}' launched safely without shell=True.",
                f"Visible window for '{target_app}' verified on interactive desktop.",
                "Action result recorded in task execution history.",
            ],
            tests_to_run=[],
            risks=(
                [f"Application '{target_app}' is verified installed on this host system."]
                if (os.getenv("LOCALAPPDATA") or os.getenv("ProgramFiles")) and SystemInspector.discover_application(target_app).is_installed
                else [f"Application '{target_app}' not installed or missing from PATH/standard locations."]
            ),
        )

    def _plan_browser_action(self, clean_task: str) -> Plan:
        """Generates a plan for opening a URL in the user's browser."""
        url = self._extract_url(clean_task)

        steps = [
            f"1. Validate URL and security constraints for '{url}'.",
            f"2. Launch default web browser and navigate to '{url}'.",
            f"3. Confirm website accessibility and record execution result.",
        ]

        tool_steps = [
            ToolStep(
                step_number=1,
                description=f"Launch default web browser and navigate to '{url}'.",
                tool="browser",
                action="open_url",
                parameters={"url": url},
                expected_outcome=f"Web browser process opens with '{url}'.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=2,
                description=f"Verify that destination URL '{url}' is accessible.",
                tool="verification",
                action="verify_url_reachable",
                parameters={"target": url},
                expected_outcome=f"HTTP connectivity to '{url}' confirmed.",
                requires_approval=False,
            ),
        ]

        return Plan(
            task=clean_task,
            summary=f"Deterministic plan for browser task: '{clean_task}'.",
            task_type="browser_action",
            steps=steps,
            tool_steps=tool_steps,
            target_url=url,
            files_to_inspect=[],
            acceptance_criteria=[
                f"Browser launched with target URL: '{url}'.",
                "Action result verified and recorded in SQLite.",
            ],
            tests_to_run=[],
            risks=["Network latency or missing internet access."],
        )

    def _plan_filesystem_action(self, clean_task: str) -> Plan:
        """Generates a plan for filesystem operations (create, list, organize)."""
        target_path = self._extract_target_path(clean_task) or "E:\\MyProject"

        steps = [
            f"1. Validate that the host drive for '{target_path}' exists and is accessible.",
            f"2. Create directory '{target_path}' on filesystem.",
            f"3. Verify that directory '{target_path}' exists on disk.",
            f"4. Record execution outcome and update task status.",
        ]

        tool_steps = [
            ToolStep(
                step_number=1,
                description=f"Create folder '{target_path}' on filesystem.",
                tool="filesystem",
                action="create_directory",
                parameters={"path": target_path, "parents": True},
                expected_outcome=f"Directory '{target_path}' created on filesystem.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=2,
                description=f"Verify that directory '{target_path}' exists on disk.",
                tool="verification",
                action="verify_path_exists",
                parameters={"target": target_path, "must_be_dir": True},
                expected_outcome=f"Directory '{target_path}' confirmed present on disk.",
                requires_approval=False,
            ),
        ]

        return Plan(
            task=clean_task,
            summary=f"Deterministic plan for filesystem task: '{clean_task}'.",
            task_type="filesystem_action",
            steps=steps,
            tool_steps=tool_steps,
            target_path=target_path,
            files_to_inspect=[],
            acceptance_criteria=[
                "Host drive verified accessible.",
                f"Directory '{target_path}' verified present on disk.",
                "Action outcome recorded in SQLite.",
            ],
            tests_to_run=[],
            risks=["Drive unmounted, unavailable, or permissions restricted."],
        )

    def _plan_composite_action(self, clean_task: str) -> Plan:
        """Generates a plan for composite actions combining filesystem and application launch."""
        target_path = self._extract_target_path(clean_task) or "E:\\MyProject"
        target_app = self._extract_app_name(clean_task)

        steps = [
            f"1. Validate that the host drive for '{target_path}' exists and is accessible.",
            f"2. Create directory '{target_path}' on filesystem.",
            f"3. Verify that directory '{target_path}' exists on disk.",
            f"4. Detect operating system and locate {target_app} executable.",
            f"5. Launch application '{target_app}' opening '{target_path}'.",
            f"6. Confirm that the launch action succeeded and update task status.",
        ]

        tool_steps = [
            ToolStep(
                step_number=1,
                description=f"Create folder '{target_path}' on filesystem.",
                tool="filesystem",
                action="create_directory",
                parameters={"path": target_path, "parents": True},
                expected_outcome=f"Directory '{target_path}' created on filesystem.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=2,
                description=f"Verify that directory '{target_path}' exists on disk.",
                tool="verification",
                action="verify_path_exists",
                parameters={"target": target_path, "must_be_dir": True},
                expected_outcome=f"Directory '{target_path}' confirmed present on disk.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=3,
                description=f"Detect whether '{target_app}' is installed and locate its executable.",
                tool="app_launcher",
                action="detect",
                parameters={"app_name": target_app},
                expected_outcome=f"Executable path for '{target_app}' discovered on host system.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=4,
                description=f"Launch application '{target_app}' opening '{target_path}'.",
                tool="app_launcher",
                action="open_in_app",
                parameters={"app_name": target_app, "target_path": target_path},
                expected_outcome=f"Application '{target_app}' launched with target folder.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=5,
                description=f"Confirm that application '{target_app}' process was created.",
                tool="verification",
                action="verify_process_running",
                parameters={"target": target_app, "app_name": target_app},
                expected_outcome=f"Process launch for '{target_app}' confirmed by operating system.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=6,
                description=f"Verify that a visible window for '{target_app}' appears on user desktop.",
                tool="verification",
                action="verify_visible_window",
                parameters={"target": target_app, "app_name": target_app, "timeout": 3.0},
                expected_outcome=f"Top-level window for '{target_app}' verified visible on interactive desktop.",
                requires_approval=False,
            ),
        ]

        return Plan(
            task=clean_task,
            summary=f"Deterministic plan for composite task: '{clean_task}'.",
            task_type="composite_action",
            steps=steps + [f"6. Verify that {target_app} window is visible on desktop."],
            tool_steps=tool_steps,
            target_path=target_path,
            target_app=target_app,
            files_to_inspect=[],
            acceptance_criteria=[
                f"Directory '{target_path}' verified present on disk.",
                f"Application '{target_app}' launched opening '{target_path}'.",
                f"Visible window for '{target_app}' verified on interactive desktop.",
                "Action results recorded in SQLite.",
            ],
            tests_to_run=[],
            risks=[
                "Drive unmounted or inaccessible.",
                f"Application '{target_app}' not installed or missing from PATH.",
            ],
        )

    def _plan_command_action(self, clean_task: str) -> Plan:
        """Generates a plan for running a shell/terminal command or git operation."""
        command, working_dir = self._extract_command_and_dir(clean_task)

        steps = [
            f"1. Validate command syntax and working directory for '{command}'.",
            f"2. Execute '{command}' in '{working_dir or 'workspace'}'.",
            f"3. Verify exit code and process output.",
        ]

        cmd_params: Dict[str, Any] = {"command": command}
        if working_dir:
            cmd_params["working_dir"] = working_dir

        tool_steps = [
            ToolStep(
                step_number=1,
                description=f"Execute '{command}'" + (f" in '{working_dir}'" if working_dir else "") + " safely.",
                tool="command",
                action="run",
                parameters=cmd_params,
                expected_outcome=f"Command '{command}' finishes execution.",
                requires_approval=False,
            ),
            ToolStep(
                step_number=2,
                description=f"Verify exit code for command '{command}'.",
                tool="verification",
                action="verify_command_result",
                parameters={"target": command},
                expected_outcome=f"Command exit code verified.",
                requires_approval=False,
            ),
        ]

        return Plan(
            task=clean_task,
            summary=f"Deterministic plan for command/git task: '{clean_task}'.",
            task_type="command_action",
            steps=steps,
            tool_steps=tool_steps,
            files_to_inspect=[],
            acceptance_criteria=[
                f"Command '{command}' executed safely.",
                "Outcome recorded in SQLite.",
            ],
            tests_to_run=[],
            risks=["Git branch collision or non-zero return code."],
        )

    def _plan_unsupported(self, clean_task: str) -> Plan:
        """Generates a plan explaining an unsupported request."""
        steps = [
            f"1. Analyze requested operation: '{clean_task}'.",
            "2. Operation cannot currently be performed safely on this system.",
        ]
        return Plan(
            task=clean_task,
            summary=f"Unsupported operation: '{clean_task}'.",
            task_type="unsupported",
            steps=steps,
            tool_steps=[],
            files_to_inspect=[],
            acceptance_criteria=["Task marked as unsupported."],
            tests_to_run=[],
            risks=["Requested operation is outside permitted capabilities."],
        )

    def _plan_code_change(self, clean_task: str) -> Plan:
        """Generates an SDLC software engineering implementation plan."""
        task_lower = clean_task.lower()

        # Deterministic file identification heuristics
        files_to_inspect: List[str] = []
        if any(keyword in task_lower for keyword in ["api", "route", "endpoint", "health", "fastapi"]):
            files_to_inspect.extend(["api/main.py", "api/routes/"])
        if any(keyword in task_lower for keyword in ["orchestrat", "workflow", "dag", "state"]):
            files_to_inspect.append("orchestrator/")
        if any(keyword in task_lower for keyword in ["agent", "planner", "coder", "reviewer"]):
            files_to_inspect.append("agents/")
        if any(keyword in task_lower for keyword in ["tool", "cli", "git", "file"]):
            files_to_inspect.append("tools/")
        if any(keyword in task_lower for keyword in ["test", "pytest", "spec"]):
            files_to_inspect.append("tests/")
        if any(keyword in task_lower for keyword in ["doc", "readme", "architecture"]):
            files_to_inspect.extend(["README.md", "docs/architecture.md"])

        # Fallback inspection candidates if none matched
        if not files_to_inspect:
            files_to_inspect = ["api/", "agents/", "tests/", "README.md"]

        # Deterministic test identification
        tests_to_run: List[str] = ["pytest -v"]
        if "health" in task_lower:
            tests_to_run.insert(0, "pytest tests/test_health.py -v")
        if "planner" in task_lower or "agent" in task_lower:
            tests_to_run.insert(0, "pytest tests/test_planner.py -v")

        steps: List[str] = [
            f"1. Analyze requirements and existing architecture for: '{clean_task}'.",
            "2. Inspect relevant candidate files and confirm contracts/interfaces.",
            "3. Implement code changes following modular, type-annotated patterns.",
            "4. Add unit and integration tests covering standard and edge-case behavior.",
            "5. Run automated test suites and verify zero regressions.",
        ]

        acceptance_criteria: List[str] = [
            f"Objective satisfied: '{clean_task}'.",
            "All new and affected code components are fully type-annotated.",
            "All unit and integration tests pass with 100% success rate.",
            "Existing endpoints and functionality remain backward-compatible.",
        ]

        risks: List[str] = [
            "Potential regressions in dependent modules or shared interfaces.",
            "Uncovered edge cases in input validation or boundary values.",
        ]
        if "database" in task_lower or "migration" in task_lower:
            risks.append("Data migration failure or breaking schema alterations.")
        if "auth" in task_lower or "security" in task_lower:
            risks.append("Security vulnerabilities or unintended permission escalation.")

        return Plan(
            task=clean_task,
            summary=f"Deterministic execution plan for task: '{clean_task}'.",
            task_type="code_change",
            steps=steps,
            tool_steps=[],
            files_to_inspect=files_to_inspect,
            acceptance_criteria=acceptance_criteria,
            tests_to_run=tests_to_run,
            risks=risks,
        )

    @staticmethod
    def _extract_app_name(text: str) -> str:
        text_lower = text.lower()
        if any(k in text_lower for k in ["vs code", "vscode", "visual studio code"]):
            return "vscode"
        if any(k in text_lower for k in ["antigravity", "agy"]):
            return "antigravity"
        if "notepad" in text_lower:
            return "notepad"
        if "sublime" in text_lower:
            return "sublime"
        if "explorer" in text_lower:
            return "explorer"
        if "powershell" in text_lower:
            return "powershell"
        if "terminal" in text_lower or "cmd" in text_lower:
            return "cmd"
        return "vscode"

    @staticmethod
    def _extract_target_path(text: str) -> Optional[str]:
        m1 = re.search(r"in (?:my )?([a-zA-Z])(?: |:)drive named ([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if m1:
            return f"{m1.group(1).upper()}:\\{m1.group(2)}"

        m2 = re.search(r"folder ([a-zA-Z0-9_\-]+) in (?:my )?([a-zA-Z])(?: |:)drive", text, re.IGNORECASE)
        if m2:
            return f"{m2.group(2).upper()}:\\{m2.group(1)}"

        m3 = re.search(r"([a-zA-Z]:[\\/][a-zA-Z0-9_\-\\./]+)", text)
        if m3:
            return m3.group(1).replace("/", "\\")

        m4 = re.search(r"named ([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
        if m4:
            return f"E:\\{m4.group(1)}"

        return None

    @staticmethod
    def _extract_url(text: str) -> str:
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            return url_match.group(0)
        text_lower = text.lower()
        if "google" in text_lower:
            return "https://www.google.com"
        if "github" in text_lower:
            return "https://github.com"
        if "stackoverflow" in text_lower:
            return "https://stackoverflow.com"
        return "https://github.com"

    @staticmethod
    def _extract_command(text: str) -> str:
        cmd, _ = PlannerAgent._extract_command_and_dir(text)
        return cmd

    @staticmethod
    def _extract_command_and_dir(text: str) -> Tuple[str, Optional[str]]:
        """Parses natural language requests into concrete git/shell command and target directory."""
        text_lower = text.lower()
        working_dir = None

        # Detect target repository or folder e.g. "invoice_gst" or path
        folder_match = re.search(r"(?:in|open|inside|into)\s+(?:my\s+)?([a-zA-Z0-9_\-\\.:/]+)(?:\s+folder|\s+repo)?", text, re.IGNORECASE)
        if folder_match:
            candidate = folder_match.group(1).strip()
            # If named invoice_gst, resolve to local project path if present
            if candidate.lower() in ("invoice_gst", "invoice-gst"):
                invoice_path = Path("E:/Project/Invoice/invoice_gst")
                if invoice_path.exists():
                    working_dir = str(invoice_path)
                else:
                    working_dir = candidate
            elif ":" in candidate or "/" in candidate or "\\" in candidate:
                working_dir = candidate

        # Check if creating or switching a git branch
        if "branch" in text_lower:
            branch_match = re.search(r"(?:branch|named|called)\s+([a-zA-Z0-9_\-\/]+)", text, re.IGNORECASE)
            branch_name = branch_match.group(1).strip() if branch_match else "feature-work"
            if branch_name.lower() in ("different", "new", "a", "my"):
                branch_name = "feature-update"

            # Check if target repository already has this branch
            if working_dir and Path(working_dir).is_dir():
                try:
                    import subprocess
                    check_proc = subprocess.run(
                        ["git", "branch", "--list", branch_name],
                        cwd=working_dir,
                        capture_output=True,
                        text=True,
                    )
                    # If branch already exists, switch to it rather than crashing on checkout -b
                    if check_proc.stdout and branch_name in check_proc.stdout:
                        return f"git checkout {branch_name}", working_dir
                except Exception:
                    pass

            command = f"git checkout -b {branch_name}"
            return command, working_dir

        if "git status" in text_lower or "check git" in text_lower:
            return "git status", working_dir

        cleaned = re.sub(r"^(?:run|execute)\s+(?:command\s+)?", "", text.strip(), flags=re.IGNORECASE)
        return cleaned.strip() or "git status", working_dir


if __name__ == "__main__":
    import json
    import sys

    sample_task = sys.argv[1] if len(sys.argv) > 1 else "Implement user authentication endpoint"
    agent = PlannerAgent()
    try:
        plan = agent.plan(sample_task)
        print(json.dumps(plan.model_dump(), indent=2))
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
