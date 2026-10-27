"""SDLC Task Lifecycle Coordinator.

Provides an internal orchestration service coordinating SDLC task lifecycle stages:
planning -> proposing -> applying changes -> verifying -> verified/failed/blocked.
Enforces explicit state transition rules and truthful verification reporting.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from agents.developer import DeveloperAgent, ImplementationProposal, RevisionProposal
from services.code_application_service import (
    CodeApplicationResult,
    CodeApplicationService,
)
from services.task_service import (
    TASK_LIFECYCLE_STATES,
    VALID_TRANSITIONS,
    InvalidStateTransitionError,
    TaskRecord,
    TaskService,
    VerificationAttemptRecord,
    VerificationDiagnostics,
    create_diagnostics_from_attempt,
)
from services.verification_service import (
    VerificationProfile,
    VerificationRequest,
    VerificationResult,
    VerificationService,
)

from agents.reviewer import CodeReviewerAgent, ReviewReport
from agents.tester import TesterAgent, TestDiagnosis, TestFrameworkDetection
from agents.architect import ArchitectAgent

DEFAULT_MAX_REVISIONS = 3


class RevisionResult(BaseModel):
    """Result of an orchestrated revision iteration."""

    task_id: str = Field(..., description="Task identifier.")
    status: str = Field(
        ...,
        description="Outcome: 'revised', 'no_action_needed', 'blocked', 'budget_exhausted', 'application_failed'.",
    )
    revision_count: int = Field(..., description="Current revision count for the task.")
    max_revisions: int = Field(..., description="Maximum allowed revision budget.")
    revision_proposal: Optional[RevisionProposal] = Field(None, description="Generated revision proposal if any.")
    application_result: Optional[CodeApplicationResult] = Field(None, description="Result of applying the patch if attempted.")
    message: str = Field(..., description="Human-readable summary of the revision outcome.")


class TaskLifecycleCoordinator:
    """Internal orchestration service managing the autonomous SDLC lifecycle for tasks."""

    def __init__(
        self,
        task_service: Optional[TaskService] = None,
        code_application_service: Optional[CodeApplicationService] = None,
        verification_service: Optional[VerificationService] = None,
        developer_agent: Optional[DeveloperAgent] = None,
        reviewer_agent: Optional[CodeReviewerAgent] = None,
        tester_agent: Optional[TesterAgent] = None,
        architect_agent: Optional[ArchitectAgent] = None,
    ) -> None:
        self.task_service: TaskService = task_service if task_service is not None else TaskService()
        self.code_application_service: CodeApplicationService = (
            code_application_service
            if code_application_service is not None
            else CodeApplicationService(task_service=self.task_service)
        )
        self.verification_service: VerificationService = (
            verification_service
            if verification_service is not None
            else VerificationService()
        )
        self.developer_agent: DeveloperAgent = (
            developer_agent
            if developer_agent is not None
            else DeveloperAgent(task_service=self.task_service)
        )
        self.reviewer_agent: CodeReviewerAgent = (
            reviewer_agent if reviewer_agent is not None else CodeReviewerAgent()
        )
        self.tester_agent: TesterAgent = (
            tester_agent if tester_agent is not None else TesterAgent()
        )
        self.architect_agent: ArchitectAgent = (
            architect_agent if architect_agent is not None else ArchitectAgent()
        )

    def propose(
        self,
        task_id: str,
        custom_proposal: Optional[ImplementationProposal] = None,
    ) -> Tuple[TaskRecord, ImplementationProposal]:
        """Generates or attaches an ImplementationProposal and transitions task to 'proposed'.

        Args:
            task_id: Unique task identifier.
            custom_proposal: Optional pre-formed proposal.

        Returns:
            Tuple of (updated TaskRecord, ImplementationProposal).

        Raises:
            ValueError: If task not found.
            InvalidStateTransitionError: If transition to 'proposed' is prohibited.
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        if custom_proposal is not None:
            proposal = custom_proposal
        else:
            proposal = self.developer_agent.generate_proposal(task)

        updated_record = self.task_service.transition_task_status(
            task_id=task_id,
            new_status="proposed",
            proposal=proposal,
            clear_error=True,
        )
        return updated_record, proposal

    def review(
        self,
        task_id: str,
        file_contents: Optional[Dict[str, str]] = None,
    ) -> Tuple[TaskRecord, ReviewReport]:
        """Audits proposed changes using CodeReviewerAgent for security and quality gates.

        Args:
            task_id: Unique task identifier.
            file_contents: Optional map of relative paths to new file contents.

        Returns:
            Tuple of (TaskRecord, ReviewReport).
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")
        if task.proposal is None:
            raise ValueError(f"Task '{task_id}' has no proposal to review.")

        report = self.reviewer_agent.review_proposal(
            proposal=task.proposal,
            file_contents=file_contents,
        )

        return task, report

    def apply(
        self,
        task_id: str,
        file_contents: Optional[Dict[str, str]] = None,
        custom_proposal: Optional[ImplementationProposal] = None,
    ) -> Tuple[TaskRecord, CodeApplicationResult]:
        """Applies code changes into an isolated workspace and updates task lifecycle.

        Args:
            task_id: Unique task identifier.
            file_contents: Optional mapping of relative file paths to new file contents.
            custom_proposal: Optional custom ImplementationProposal to apply.

        Returns:
            Tuple of (updated TaskRecord, CodeApplicationResult).

        Raises:
            ValueError: If task not found.
            InvalidStateTransitionError: If transition to 'changes_applied' is prohibited.
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        result = self.code_application_service.apply_proposal(
            task_id=task_id,
            file_contents=file_contents,
            custom_proposal=custom_proposal,
        )

        if result.status == "applied":
            updated_record = self.task_service.transition_task_status(
                task_id=task_id,
                new_status="changes_applied",
                workspace_id=result.workspace_id,
                application_status="applied",
                clear_error=True,
            )
        else:
            # Application failed or partially failed; record status and error summary without transitioning state
            error_msg = "; ".join(result.errors) if result.errors else "Code application failed"
            self.task_service.db.update_task_fields(
                task_id=task_id,
                updated_at=task.updated_at,
                application_status=result.status,
                error_summary=error_msg,
            )
            updated_record = self.task_service.get_task(task_id)  # type: ignore[assignment]

        return updated_record, result

    def verify(
        self,
        task_id: str,
        profile: VerificationProfile = "pytest_standard",
        timeout_seconds: Optional[float] = None,
    ) -> Tuple[TaskRecord, VerificationResult]:
        """Verifies an applied workspace, logs historical outcome, and transitions task state.

        Adheres strictly to truthful status reporting:
        - 'verified' is ONLY set when an actual test process executed and exited with code 0.
        - 'verification_failed' is set when an actual test process executed and exited with non-zero code.
        - 'verification_blocked' is set when security policy or lack of isolation prevented execution.
        - 'verification_timed_out' is set when process exceeded timeout.
        - 'verification_error' is set when an environment or runner error occurred.

        Args:
            task_id: Unique task identifier.
            profile: Approved verification profile to execute.
            timeout_seconds: Optional execution timeout in seconds.

        Returns:
            Tuple of (updated TaskRecord, VerificationResult).

        Raises:
            ValueError: If task not found or workspace is missing.
            InvalidStateTransitionError: If verification cannot be initiated from current state.
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        if not task.workspace_id:
            raise ValueError(
                f"Task '{task_id}' has no associated workspace. Cannot verify unapplied changes."
            )

        # Transition task to 'verifying'
        self.task_service.transition_task_status(
            task_id=task_id,
            new_status="verifying",
        )

        request_kwargs = {"workspace_id": task.workspace_id, "profile": profile}
        if timeout_seconds is not None:
            request_kwargs["timeout_seconds"] = timeout_seconds

        request = VerificationRequest(**request_kwargs)
        verification_result = self.verification_service.verify_workspace(request)

        # Record attempt in persistent verification history
        self.task_service.record_verification_attempt(task_id, verification_result)

        # Determine target state based strictly on actual outcome
        if verification_result.status == "passed" and verification_result.exit_code == 0:
            target_status = "verified"
        elif verification_result.status == "failed":
            target_status = "verification_failed"
        elif verification_result.status == "blocked":
            target_status = "verification_blocked"
        elif verification_result.status == "timed_out":
            target_status = "verification_timed_out"
        else:
            target_status = "verification_error"

        updated_record = self.task_service.transition_task_status(
            task_id=task_id,
            new_status=target_status,
            verification_status=verification_result.status,
            error_summary=verification_result.error_message,
        )

        return updated_record, verification_result

    def get_verification_history(self, task_id: str) -> List[VerificationAttemptRecord]:
        """Retrieves all verification attempts for a task in chronological order.

        Args:
            task_id: Unique task identifier.

        Returns:
            List of VerificationAttemptRecord objects.
        """
        return self.task_service.get_verification_history(task_id)

    def revise(
        self,
        task_id: str,
        auto_verify: bool = False,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
        suggested_patches: Optional[Dict[str, str]] = None,
        profile: VerificationProfile = "pytest_standard",
    ) -> Tuple[TaskRecord, RevisionResult, Optional[VerificationResult]]:
        """Orchestrates a single targeted patch revision based on the latest verification diagnostics.

        Enforces bounded revision budget, truthful diagnostic handling, and safe path application.
        Does NOT automatically execute verification unless explicitly requested via auto_verify=True.

        Args:
            task_id: Unique task identifier.
            auto_verify: Whether to immediately run verification after applying the patch.
            max_revisions: Maximum allowed revision budget.
            suggested_patches: Optional explicit mapping of {relative_path: patch_content}.
            profile: Approved verification profile if auto_verify is requested.

        Returns:
            Tuple of (updated TaskRecord, RevisionResult, Optional[VerificationResult]).

        Raises:
            ValueError: If task not found or paths violate safety constraints.
        """
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        # 1. Enforce Bounded Revision Budget
        if task.revision_count >= max_revisions:
            result = RevisionResult(
                task_id=task_id,
                status="budget_exhausted",
                revision_count=task.revision_count,
                max_revisions=max_revisions,
                message=f"Revision budget exhausted ({task.revision_count}/{max_revisions}). Further automated retries refused.",
            )
            return task, result, None

        # 2. Check applicable diagnostics
        latest_verif = task.latest_verification
        if latest_verif is None:
            result = RevisionResult(
                task_id=task_id,
                status="no_action_needed",
                revision_count=task.revision_count,
                max_revisions=max_revisions,
                message="No verification attempt found for task. Cannot revise without diagnostics.",
            )
            return task, result, None

        if latest_verif.status == "blocked":
            result = RevisionResult(
                task_id=task_id,
                status="blocked",
                revision_count=task.revision_count,
                max_revisions=max_revisions,
                message="Latest verification attempt was blocked by security policy; cannot treat as code defect.",
            )
            return task, result, None

        if latest_verif.status == "passed" and latest_verif.exit_code == 0:
            result = RevisionResult(
                task_id=task_id,
                status="no_action_needed",
                revision_count=task.revision_count,
                max_revisions=max_revisions,
                message="Latest verification passed; no corrective revision is required.",
            )
            return task, result, None

        # 3. Formulate revision proposal from diagnostics
        diagnostics = create_diagnostics_from_attempt(latest_verif)
        revision_proposal = self.developer_agent.revise_from_diagnostics(
            task_record=task,
            diagnostics=diagnostics,
            suggested_patches=suggested_patches,
        )

        if not revision_proposal.can_revise or not revision_proposal.proposed_changes:
            result = RevisionResult(
                task_id=task_id,
                status="no_action_needed",
                revision_count=task.revision_count,
                max_revisions=max_revisions,
                revision_proposal=revision_proposal,
                message=revision_proposal.explanation,
            )
            return task, result, None

        # 4. Construct ImplementationProposal for the revision
        impl_proposal = ImplementationProposal(
            task_id=task_id,
            task=task.task,
            status="proposed",
            summary=revision_proposal.explanation,
            files_to_change=revision_proposal.proposed_changes,
            execution_steps=[f"Apply corrective revision: {revision_proposal.explanation}"],
            verification_commands=[f"pytest -v ({revision_proposal.test_strategy})"],
            dry_run=False,
        )

        # 5. Transition task state to 'proposed'
        self.task_service.transition_task_status(
            task_id=task_id,
            new_status="proposed",
            proposal=impl_proposal,
        )

        # 6. Apply revision to workspace
        updated_task, app_result = self.apply(
            task_id=task_id,
            file_contents=revision_proposal.suggested_file_contents,
            custom_proposal=impl_proposal,
        )

        # 7. Increment persistent revision count
        new_revision_count = task.revision_count + 1
        now = datetime.now(timezone.utc).isoformat()
        self.task_service.db.update_task_fields(
            task_id=task_id,
            updated_at=now,
            revision_count=new_revision_count,
        )
        updated_task = self.task_service.get_task(task_id)  # type: ignore[assignment]

        if app_result.status != "applied":
            result = RevisionResult(
                task_id=task_id,
                status="application_failed",
                revision_count=new_revision_count,
                max_revisions=max_revisions,
                revision_proposal=revision_proposal,
                application_result=app_result,
                message="Failed applying revision patch to isolated workspace.",
            )
            return updated_task, result, None

        # 8. Check auto_verify
        verif_result = None
        if auto_verify:
            updated_task, verif_result = self.verify(task_id=task_id, profile=profile)
            message = (
                f"Revision {new_revision_count}/{max_revisions} applied and verified "
                f"(status={verif_result.status})."
            )
        else:
            message = (
                f"Revision {new_revision_count}/{max_revisions} applied successfully. "
                f"Ready for verification."
            )

        result = RevisionResult(
            task_id=task_id,
            status="revised",
            revision_count=new_revision_count,
            max_revisions=max_revisions,
            revision_proposal=revision_proposal,
            application_result=app_result,
            message=message,
        )
        return updated_task, result, verif_result

    def run_revision_loop(
        self,
        task_id: str,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
        profile: VerificationProfile = "pytest_standard",
        suggested_patches: Optional[Dict[str, str]] = None,
    ) -> Tuple[TaskRecord, RevisionResult, List[VerificationResult]]:
        """Coordinates bounded revision loop alternating revision and verification until resolved or budget exhausted.

        Args:
            task_id: Unique task identifier.
            max_revisions: Maximum number of revision attempts allowed.
            profile: Approved verification profile to execute.
            suggested_patches: Optional explicit mapping of {relative_path: patch_content}.

        Returns:
            Tuple of (final TaskRecord, final RevisionResult, list of VerificationResults).
        """
        verification_results: List[VerificationResult] = []
        task = self.task_service.get_task(task_id)
        if task is None:
            raise ValueError(f"Task with ID '{task_id}' not found.")

        final_rev_result: Optional[RevisionResult] = None

        while True:
            task, rev_result, verif_result = self.revise(
                task_id=task_id,
                auto_verify=True,
                max_revisions=max_revisions,
                suggested_patches=suggested_patches,
                profile=profile,
            )
            final_rev_result = rev_result
            if verif_result is not None:
                verification_results.append(verif_result)

            # Terminate loop conditions:
            # 1. Could not revise further (e.g. no action, blocked, budget exhausted, app failure)
            if rev_result.status != "revised":
                break
            # 2. Task became verified
            if task.status == "verified":
                break
            # 3. Verification was blocked or encountered an unexpected runner error
            if verif_result and verif_result.status in ("blocked", "error"):
                break

        return task, final_rev_result, verification_results
