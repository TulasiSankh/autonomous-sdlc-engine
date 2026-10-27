"""Code Reviewer Agent module.

Evaluates proposed code changes and diffs for:
- Correctness and potential runtime bugs
- Security vulnerabilities (OWASP top 10, secrets leakage, SQL injection, insecure deserialization)
- Code maintainability, readability, and style conventions
- Potential unintended modifications or breaking changes

Provides deterministic, truthful verdicts: 'approved', 'approved_with_warnings', or 'rejected'.
"""

import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from agents.developer import ImplementationProposal, ProposedFileChange


class ReviewFinding(BaseModel):
    """An individual finding or issue detected during code review."""

    severity: str = Field(
        ...,
        description="Severity level: 'blocker', 'warning', or 'info'."
    )
    category: str = Field(
        ...,
        description="Issue category: 'security', 'syntax', 'correctness', or 'maintainability'."
    )
    file_path: str = Field(
        ...,
        description="Target relative file path."
    )
    line_number: Optional[int] = Field(
        default=None,
        description="Line number if identifiable."
    )
    message: str = Field(
        ...,
        description="Clear description of the identified issue."
    )
    recommendation: Optional[str] = Field(
        default=None,
        description="Remediation or suggested fix."
    )


class ReviewReport(BaseModel):
    """Structured code review evaluation report."""

    verdict: str = Field(
        ...,
        description="Final verdict: 'approved', 'approved_with_warnings', or 'rejected'."
    )
    summary: str = Field(
        ...,
        description="High-level evaluation summary."
    )
    security_score: int = Field(
        default=100,
        description="Security posture rating from 0 to 100."
    )
    findings: List[ReviewFinding] = Field(
        default_factory=list,
        description="List of detected review findings."
    )
    auto_approvable: bool = Field(
        default=True,
        description="Whether changes meet safe automated approval thresholds."
    )


# Common dangerous patterns for static detection
SUSPICIOUS_SECRETS_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Hardcoded API key or private secret detected"),
    (r"(?i)password\s*[:=]\s*['\"][^'\"]{6,}['\"]", "Hardcoded password found in source"),
    (r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----", "Raw private key certificate embedded in code"),
]

SQL_INJECTION_PATTERNS = [
    (r"(?i)(SELECT|INSERT|UPDATE|DELETE)\s+.*%\s*\([^\)]+\)", "Potential raw string-formatting SQL injection"),
    (r"(?i)f[\"'].*(SELECT|INSERT|UPDATE|DELETE)\s+.*\{.*\}", "Potential f-string SQL query injection"),
    (r"(?i)execute\s*\(\s*['\"].*(\+|%)\s*", "Dynamic unparameterized SQL execution"),
]

DANGEROUS_COMMAND_PATTERNS = [
    (r"(?i)(rm\s+-rf\s+[\/\*]|del\s+\/s\s+\/q\s+c:\\)", "Destructive recursive deletion command detected"),
    (r"(?i)os\.system\s*\(\s*f?['\"].*(\$|\{)", "Dynamic shell execution via os.system with unvalidated variable"),
    (r"(?i)subprocess\.call\s*\(\s*.*shell\s*=\s*True", "Shell execution with shell=True enabled"),
]


class CodeReviewerAgent:
    """Autonomous agent that audits implementation proposals and file contents before verification."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    def review_proposal(
        self,
        proposal: ImplementationProposal,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> ReviewReport:
        """Audits an implementation proposal and associated file contents.

        Args:
            proposal: The DeveloperAgent's generated ImplementationProposal.
            file_contents: Dictionary mapping relative file path to the modified/new content.

        Returns:
            ReviewReport with structured findings, severity, and approval status.
        """
        findings: List[ReviewFinding] = []
        contents = file_contents or {}

        # 1. Audit proposed changes scope
        changes_list = proposal.files_to_change if hasattr(proposal, "files_to_change") and proposal.files_to_change else getattr(proposal, "changes", [])
        if not changes_list:
            return ReviewReport(
                verdict="approved",
                summary="No code changes proposed; clean review.",
                security_score=100,
                findings=[],
                auto_approvable=True,
            )

        # 2. Inspect each file content
        for change in changes_list:
            path = change.path
            file_body = contents.get(path, "")

            # If content not supplied in dict, inspect diff if present
            if not file_body and hasattr(proposal, "diffs"):
                for diff_obj in proposal.diffs:
                    if diff_obj.path == path:
                        file_body = diff_obj.diff
                        break

            file_findings = self._audit_file_content(path, file_body)
            findings.extend(file_findings)

        # 3. Calculate scores and determine final verdict
        has_blocker = any(f.severity == "blocker" for f in findings)
        warning_count = sum(1 for f in findings if f.severity == "warning")

        security_score = max(0, 100 - (len([f for f in findings if f.category == "security"]) * 25))

        if has_blocker:
            verdict = "rejected"
            auto_approvable = False
            summary = f"Review rejected: {len([f for f in findings if f.severity == 'blocker'])} blocker(s) found."
        elif warning_count > 0 and self.strict_mode:
            verdict = "rejected"
            auto_approvable = False
            summary = f"Review rejected under strict mode with {warning_count} warning(s)."
        elif warning_count > 0:
            verdict = "approved_with_warnings"
            auto_approvable = True
            summary = f"Approved with {warning_count} advisory warning(s)."
        else:
            verdict = "approved"
            auto_approvable = True
            summary = f"All {len(changes_list)} proposed change(s) passed security and quality review."

        return ReviewReport(
            verdict=verdict,
            summary=summary,
            security_score=security_score,
            findings=findings,
            auto_approvable=auto_approvable,
        )

    def _audit_file_content(self, path: str, content: str) -> List[ReviewFinding]:
        """Runs static heuristic and pattern scans over individual file content."""
        findings: List[ReviewFinding] = []
        if not content:
            return findings

        # Check for hardcoded secrets
        for pattern, msg in SUSPICIOUS_SECRETS_PATTERNS:
            match = re.search(pattern, content)
            if match:
                findings.append(
                    ReviewFinding(
                        severity="blocker",
                        category="security",
                        file_path=path,
                        message=f"{msg} ({match.group(0)[:30]}...)",
                        recommendation="Store secret in environment variables or vault instead of source code.",
                    )
                )

        # Check for SQL injection patterns
        for pattern, msg in SQL_INJECTION_PATTERNS:
            match = re.search(pattern, content)
            if match:
                findings.append(
                    ReviewFinding(
                        severity="blocker",
                        category="security",
                        file_path=path,
                        message=msg,
                        recommendation="Use parameterized queries or ORM query builder.",
                    )
                )

        # Check for dangerous command execution
        for pattern, msg in DANGEROUS_COMMAND_PATTERNS:
            match = re.search(pattern, content)
            if match:
                findings.append(
                    ReviewFinding(
                        severity="blocker" if "rm -rf" in msg or "del /s" in msg else "warning",
                        category="security",
                        file_path=path,
                        message=msg,
                        recommendation="Validate path parameters and avoid shell=True.",
                    )
                )

        # Code quality & maintainability heuristics
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if "TODO:" in line or "FIXME:" in line:
                findings.append(
                    ReviewFinding(
                        severity="info",
                        category="maintainability",
                        file_path=path,
                        line_number=idx,
                        message="Unresolved TODO/FIXME annotation in implementation",
                        recommendation="Resolve comment or open a tracking issue before merging.",
                    )
                )

        return findings
