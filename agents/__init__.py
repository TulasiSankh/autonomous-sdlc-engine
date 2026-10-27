"""Agents package.

Defines role-based autonomous agents (e.g., Planner, Developer, Reviewer, QA)
and their individual decision-making loops.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.developer import (
        DeveloperAgent,
        ImplementationProposal,
        ProposedFileChange,
        validate_relative_path,
    )
    from agents.planner import Plan, PlannerAgent
    from agents.reviewer import CodeReviewerAgent, ReviewReport, ReviewFinding
    from agents.tester import TesterAgent, TestDiagnosis, TestFrameworkDetection
    from agents.architect import ArchitectAgent, ProjectTemplate


def __getattr__(name: str):
    if name in ("Plan", "PlannerAgent"):
        from agents.planner import Plan, PlannerAgent

        items = {"Plan": Plan, "PlannerAgent": PlannerAgent}
        return items[name]

    if name in (
        "DeveloperAgent",
        "ImplementationProposal",
        "ProposedFileChange",
        "validate_relative_path",
    ):
        from agents.developer import (
            DeveloperAgent,
            ImplementationProposal,
            ProposedFileChange,
            validate_relative_path,
        )

        items = {
            "DeveloperAgent": DeveloperAgent,
            "ImplementationProposal": ImplementationProposal,
            "ProposedFileChange": ProposedFileChange,
            "validate_relative_path": validate_relative_path,
        }
        return items[name]

    if name in ("CodeReviewerAgent", "ReviewReport", "ReviewFinding"):
        from agents.reviewer import CodeReviewerAgent, ReviewReport, ReviewFinding

        items = {
            "CodeReviewerAgent": CodeReviewerAgent,
            "ReviewReport": ReviewReport,
            "ReviewFinding": ReviewFinding,
        }
        return items[name]

    if name in ("TesterAgent", "TestDiagnosis", "TestFrameworkDetection"):
        from agents.tester import TesterAgent, TestDiagnosis, TestFrameworkDetection

        items = {
            "TesterAgent": TesterAgent,
            "TestDiagnosis": TestDiagnosis,
            "TestFrameworkDetection": TestFrameworkDetection,
        }
        return items[name]

    if name in ("ArchitectAgent", "ProjectTemplate"):
        from agents.architect import ArchitectAgent, ProjectTemplate

        items = {
            "ArchitectAgent": ArchitectAgent,
            "ProjectTemplate": ProjectTemplate,
        }
        return items[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Plan",
    "PlannerAgent",
    "DeveloperAgent",
    "ImplementationProposal",
    "ProposedFileChange",
    "validate_relative_path",
    "CodeReviewerAgent",
    "ReviewReport",
    "ReviewFinding",
    "TesterAgent",
    "TestDiagnosis",
    "TestFrameworkDetection",
    "ArchitectAgent",
    "ProjectTemplate",
]
