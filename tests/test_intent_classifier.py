"""Unit tests for TaskIntentClassifier."""

import pytest
from agents.intent_classifier import TaskIntentClassifier


def test_classify_application_action():
    assert TaskIntentClassifier.classify("Open VS Code") == "application_action"
    assert TaskIntentClassifier.classify("open the vs code") == "application_action"
    assert TaskIntentClassifier.classify("open my vs code") == "application_action"
    assert TaskIntentClassifier.classify("Launch VS Code") == "application_action"
    assert TaskIntentClassifier.classify("Open Antigravity") == "application_action"
    assert TaskIntentClassifier.classify("Launch Antigravity") == "application_action"
    assert TaskIntentClassifier.classify("Open Notepad") == "application_action"
    assert TaskIntentClassifier.classify("open the notepad") == "application_action"
    assert TaskIntentClassifier.classify("Start visual studio code") == "application_action"


def test_classify_browser_action():
    assert TaskIntentClassifier.classify("Open my GitHub") == "browser_action"
    assert TaskIntentClassifier.classify("Open GitHub in the default browser") == "browser_action"
    assert TaskIntentClassifier.classify("Browse to https://github.com") == "browser_action"
    assert TaskIntentClassifier.classify("Open google.com in browser") == "browser_action"
    assert TaskIntentClassifier.classify("Navigate to https://example.com") == "browser_action"


def test_classify_filesystem_action():
    assert TaskIntentClassifier.classify("Create a folder named MyProject in E drive") == "filesystem_action"
    assert TaskIntentClassifier.classify("Create folder E:\\NewProject") == "filesystem_action"
    assert TaskIntentClassifier.classify("Make directory docs") == "filesystem_action"
    assert TaskIntentClassifier.classify("List files in E:\\MyProject") == "filesystem_action"
    assert TaskIntentClassifier.classify("Rename folder Old to New") == "filesystem_action"


def test_classify_composite_action():
    assert (
        TaskIntentClassifier.classify("Create a folder named MyProject in E drive and open it in VS Code")
        == "composite_action"
    )
    assert (
        TaskIntentClassifier.classify("Create a folder in my E drive named MyProject and open it in VS Code")
        == "composite_action"
    )
    assert (
        TaskIntentClassifier.classify("Create a folder E:\\Project and open it in Antigravity")
        == "composite_action"
    )


def test_classify_code_change():
    assert TaskIntentClassifier.classify("Create a Python calculator") == "code_change"
    assert TaskIntentClassifier.classify("Add a GET /api/version endpoint") == "code_change"
    assert TaskIntentClassifier.classify("Implement user authentication with JWT") == "code_change"
    assert TaskIntentClassifier.classify("Fix bug in calculation logic") == "code_change"
    assert TaskIntentClassifier.classify("Refactor the database connection handler") == "code_change"


def test_classify_command_action():
    assert TaskIntentClassifier.classify("Run git status") == "command_action"
    assert TaskIntentClassifier.classify("Run command ping google.com") == "command_action"
    assert TaskIntentClassifier.classify("Execute dir") == "command_action"


def test_classify_unsupported():
    assert TaskIntentClassifier.classify("Shutdown computer") == "unsupported"
    assert TaskIntentClassifier.classify("Format drive C:") == "unsupported"
    assert TaskIntentClassifier.classify("Order food from restaurant") == "unsupported"
    assert TaskIntentClassifier.classify("") == "unsupported"
