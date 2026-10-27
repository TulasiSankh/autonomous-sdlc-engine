"""Tests for tool registry and individual computer tools."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.app_launcher_tool import AppLauncherTool
from tools.base import ToolExecutionResult
from tools.browser_tool import BrowserTool
from tools.command_tool import CommandTool
from tools.filesystem_tool import FilesystemTool
from tools.registry import ToolRegistry, get_default_registry
from tools.verification_tool import VerificationTool


def test_registry_registration_and_discovery():
    registry = ToolRegistry()
    browser = BrowserTool()
    registry.register_tool(browser)

    assert registry.get_tool("browser") is browser
    assert registry.get_tool("nonexistent") is None

    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "browser"
    assert "open_url" in tools[0]["supported_actions"]


def test_default_registry_has_all_five_tools():
    reg = get_default_registry()
    expected = ["browser", "filesystem", "app_launcher", "command", "verification"]
    for tool_name in expected:
        tool = reg.get_tool(tool_name)
        assert tool is not None, f"Expected tool '{tool_name}' in default registry"


def test_browser_tool_validation():
    tool = BrowserTool()

    # Invalid URL scheme
    res = tool.execute("open_url", {"url": "ftp://example.com"})
    assert not res.success
    assert "http" in res.error.lower()

    # Missing URL parameter
    res = tool.execute("open_url", {})
    assert not res.success
    assert "Missing required parameter" in res.error

    # Dangerous characters in URL
    res = tool.execute("open_url", {"url": "https://example.com; rm -rf /"})
    assert not res.success
    assert "dangerous characters" in res.error


def test_browser_tool_launch_mocked():
    mock_launcher = MagicMock(return_value=True)
    tool = BrowserTool(browser_launcher=mock_launcher)

    res = tool.execute("open_url", {"url": "https://github.com"})
    assert res.success
    mock_launcher.assert_called_once_with("https://github.com")
    assert res.output["url"] == "https://github.com"


def test_filesystem_tool_create_directory_and_verify():
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = FilesystemTool()
        new_dir = os.path.join(tmpdir, "MyProject", "subfolder")

        res = tool.execute("create_directory", {"path": new_dir})
        assert res.success
        assert os.path.isdir(new_dir)

        # Check path_exists
        res = tool.execute("path_exists", {"path": new_dir})
        assert res.success
        assert res.output["exists"] is True


def test_filesystem_tool_missing_drive_windows():
    tool = FilesystemTool()
    # Drive 9:\ is virtually guaranteed not to exist
    fake_path = "9:\\NonExistentDriveFolder\\Project"

    with patch("os.path.exists", side_effect=lambda p: False if "9:" in str(p) else True):
        res = tool.execute("create_directory", {"path": fake_path})
        assert not res.success
        assert "drive" in res.error.lower() or "does not exist" in res.error.lower()


def test_filesystem_tool_read_write_bounds():
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = FilesystemTool()
        file_path = os.path.join(tmpdir, "test.txt")

        # Write
        res = tool.execute("write_file", {"path": file_path, "content": "Hello Orbit AI"})
        assert res.success

        # Read
        res = tool.execute("read_file", {"path": file_path})
        assert res.success
        assert res.output["content"] == "Hello Orbit AI"


def test_app_launcher_missing_application():
    tool = AppLauncherTool()
    # Explicitly clear env vars and search
    with patch.dict(os.environ, {}, clear=True), patch("shutil.which", return_value=None):
        res = tool.execute("launch", {"app_name": "nonexistent_editor_app", "target_path": "C:\\"})
        assert not res.success
        assert "not found" in res.error.lower()


def test_app_launcher_supported_app_detection():
    tool = AppLauncherTool()
    with patch.object(tool, "find_executable", return_value="C:\\FakePath\\code.exe"):
        res = tool.execute("detect", {"app_name": "vscode"})
        assert res.success
        assert res.output["detected"] is True
        assert res.output["path"] == "C:\\FakePath\\code.exe"


def test_command_tool_execution_success():
    tool = CommandTool()
    # Simple safe echo
    res = tool.execute("execute", {"command": "echo OrbitComputerAgent"})
    assert res.success
    assert "OrbitComputerAgent" in res.output["stdout"]
    assert res.output["exit_code"] == 0


def test_command_tool_disallowed_destructive_command():
    tool = CommandTool()
    res = tool.execute("execute", {"command": "format c:"})
    assert not res.success
    assert "blocked" in res.error.lower() or "disallowed" in res.error.lower()


def test_verification_tool_path_and_url():
    vtool = VerificationTool()

    with tempfile.TemporaryDirectory() as tmpdir:
        res = vtool.execute("verify_path_exists", {"path": tmpdir})
        assert res.success
        assert res.output["exists"] is True

        res = vtool.execute("verify_path_exists", {"path": os.path.join(tmpdir, "ghost")})
        assert not res.success
        assert res.output["exists"] is False
