"""Task intent classification module for Orbit AI.

Classifies natural-language user tasks into specific operational categories:
- browser_action: open a website or navigate to a URL.
- filesystem_action: create, list, rename, or organize files and folders.
- application_action: launch or open an installed desktop application.
- command_action: run a requested command or program.
- code_change: modify or create software source code.
- composite_action: execute a task containing multiple action types.
- unsupported: the requested operation cannot currently be performed.
"""

import re
from typing import List, Literal, Set

TaskIntent = Literal[
    "browser_action",
    "filesystem_action",
    "application_action",
    "command_action",
    "code_change",
    "composite_action",
    "unsupported",
]

# Known desktop application aliases
KNOWN_APPS = {
    "vs code",
    "vscode",
    "visual studio code",
    "code",
    "antigravity",
    "agy",
    "notepad",
    "sublime",
    "sublime text",
    "explorer",
    "terminal",
    "cmd",
    "powershell",
    "cursor",
}

# Browser action indicators
BROWSER_TRIGGERS = [
    "open my github",
    "open github",
    "go to github",
    "open browser",
    "open the browser",
    "open my browser",
    "open website",
    "open url",
    "in browser",
    "in the browser",
    "in default browser",
    "browse to",
    "navigate to",
    "open youtube",
    "open google",
    "google.com",
    "github.com",
    "stackoverflow.com",
]

# Filesystem action indicators
FILESYSTEM_TRIGGERS = [
    "create a folder",
    "create folder",
    "make a folder",
    "make folder",
    "create directory",
    "make directory",
    "create a directory",
    "list files",
    "list folders",
    "list directory",
    "rename folder",
    "rename file",
    "delete folder",
    "delete file",
    "organize files",
    "move file",
    "copy file",
]

# Command execution triggers
COMMAND_TRIGGERS = [
    "run command",
    "execute command",
    "run shell",
    "run in terminal",
    "run ping",
    "run git",
    "git status",
    "check git",
    "git checkout",
    "git branch",
    "create a branch",
    "create a different branch",
    "create branch",
    "switch branch",
    "open my folder",
    "open folder",
    "run pytest",
    "run backend tests",
    "run tests",
    "run test",
    "run npm",
    "run python",
    "run my next",
    "run next",
    "run next.js",
    "run application",
    "run the application",
    "run dev",
    "run start",
    "inspect application errors",
    "inspect errors",
    "check application errors",
    "check errors",
    "execute ",
]

# Code change triggers
CODE_CHANGE_TRIGGERS = [
    "create a python",
    "build a",
    "implement",
    "write code",
    "write a script",
    "write a python",
    "create a calculator",
    "add endpoint",
    "add a get",
    "add a post",
    "create endpoint",
    "add route",
    "fix bug",
    "refactor",
    "unit test",
    "write tests",
    "create module",
    "add function",
    "write function",
    "create class",
]

# Dangerous or currently unsupported computer actions
UNSUPPORTED_TRIGGERS = [
    "shutdown",
    "restart computer",
    "format c:",
    "format drive",
    "delete system32",
    "send email",
    "send message",
    "order food",
    "book a flight",
    "hack",
]


class TaskIntentClassifier:
    """Deterministic, rule-based intent classifier for computer tasks and engineering requests."""

    @classmethod
    def classify(cls, task_description: str) -> TaskIntent:
        """Classifies a sanitized task description into an explicit TaskIntent.

        Args:
            task_description: Natural-language task input from user.

        Returns:
            One of the 7 supported TaskIntent categories.
        """
        if not task_description or not isinstance(task_description, str):
            return "unsupported"

        task_lower = task_description.strip().lower()

        # 0. Check for unsupported/dangerous tasks
        if any(unsupp in task_lower for unsupp in UNSUPPORTED_TRIGGERS):
            return "unsupported"

        # Detect constituent action categories
        has_browser = cls._matches_browser(task_lower)
        has_filesystem = cls._matches_filesystem(task_lower)
        has_application = cls._matches_application(task_lower)
        has_command = cls._matches_command(task_lower)
        has_code_change = cls._matches_code_change(task_lower)

        # 1. Composite Actions: contains multiple distinct computer actions
        detected_actions = sum([
            bool(has_browser),
            bool(has_filesystem),
            bool(has_application),
            bool(has_command),
        ])

        if detected_actions >= 2:
            return "composite_action"

        # Special check: folder + open in app (e.g. "Create a folder named MyProject in E drive and open it in VS Code")
        if has_filesystem and ("open in" in task_lower or "open it in" in task_lower or any(app in task_lower for app in KNOWN_APPS)):
            return "composite_action"

        # 2. Browser Action (e.g. "Open my GitHub", "Browse to https://...")
        if has_browser and not has_filesystem and not has_code_change:
            return "browser_action"

        # 3. Application Action (e.g. "Open VS Code", "Launch Antigravity", "Open Notepad")
        if has_application and not has_filesystem and not has_code_change:
            return "application_action"

        # 4. Filesystem Action (e.g. "Create a folder named MyProject in E drive", "List files in E:\MyProject")
        if has_filesystem and not has_code_change:
            return "filesystem_action"

        # 5. Command Action (e.g. "Run git status", "Execute command ping google.com")
        if has_command and not has_code_change:
            return "command_action"

        # 6. Code Change (e.g. "Create a Python calculator", "Add a GET /api/version endpoint")
        if has_code_change:
            return "code_change"

        # Secondary heuristics: check if user explicitly mentions code-building nouns
        code_nouns = ["endpoint", "api", "function", "class", "algorithm", "calculator", "database", "migration"]
        if any(w in task_lower for w in code_nouns):
            return "code_change"

        # Default fallback: if task mentions URLs/websites
        if re.search(r"https?://[^\s]+", task_lower):
            return "browser_action"

        # Fallback to code_change if it seems like a development request
        return "code_change"

    @classmethod
    def _matches_browser(cls, text: str) -> bool:
        if text.startswith(("run command", "execute command", "ping ", "curl ", "wget ")):
            return False
        if any(cmd in text for cmd in ["ping ", "curl ", "wget ", "traceroute "]):
            return False
        if any(trigger in text for trigger in BROWSER_TRIGGERS):
            return True
        if re.search(r"\b(open|browse|navigate|visit)\s+(https?://[^\s]+|[a-z0-9\-]+\.(com|org|net|io|dev|edu))\b", text):
            return True
        return False

    @classmethod
    def _matches_filesystem(cls, text: str) -> bool:
        if any(trigger in text for trigger in FILESYSTEM_TRIGGERS):
            return True
        # Path manipulation patterns like "in E drive named X"
        if re.search(r"in (?:my )?[a-z](?: |:)drive named [a-z0-9_\-]+", text):
            return True
        if re.search(r"folder [a-z0-9_\-]+ in (?:my )?[a-z](?: |:)drive", text):
            return True
        if re.search(r"\b(mkdir|rmdir|touch)\s+[a-z0-9_\\\-/]+", text):
            return True
        return False

    @classmethod
    def _matches_application(cls, text: str) -> bool:
        # e.g. "Open VS Code", "Open the VS Code", "Open my VS Code", "Launch Antigravity", "Open Notepad"
        launch_verbs = ["open", "launch", "start", "run"]
        # Allow optional determiners/pronouns like "the", "my", "our", "an", "a"
        determiners_pattern = r"(?:(?:it\s+in|in|with)\s+)?(?:the\s+|my\s+|our\s+|a\s+|an\s+)?"
        for verb in launch_verbs:
            for app in KNOWN_APPS:
                # Match "open vs code", "open the vs code", "open my vs code", "launch vscode"
                if re.search(rf"\b{verb}\s+{determiners_pattern}{re.escape(app)}\b", text):
                    return True
        # Explicit "open in <app>", "open with <app>", "in the <app>"
        for app in KNOWN_APPS:
            if re.search(rf"\b(?:in|with)\s+(?:the\s+|my\s+)?{re.escape(app)}\b", text):
                return True
        return False

    @classmethod
    def _matches_command(cls, text: str) -> bool:
        if any(trigger in text for trigger in COMMAND_TRIGGERS):
            return True
        if text.startswith("run ") or text.startswith("execute "):
            # Avoid "run a python script that calculates" when it means build it
            if not any(k in text for k in ["build", "create", "implement", "write"]):
                return True
        return False

    @classmethod
    def _matches_code_change(cls, text: str) -> bool:
        if any(trigger in text for trigger in CODE_CHANGE_TRIGGERS):
            return True
        if any(text.startswith(prefix) for prefix in ["create a python", "write a python", "implement", "build a", "fix bug"]):
            return True
        return False
