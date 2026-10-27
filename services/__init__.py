"""Services package for the Autonomous SDLC Engine."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.code_application_service import (
        CodeApplicationResult,
        CodeApplicationService,
        FileDiff,
        generate_unified_diff,
    )
    from services.lifecycle_service import (
        DEFAULT_MAX_REVISIONS,
        RevisionResult,
        TaskLifecycleCoordinator,
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
        BaseVerificationRunner,
        DisabledSecurityRunner,
        SubprocessSandboxRunner,
        VerificationProfile,
        VerificationRequest,
        VerificationResult,
        VerificationService,
        VerificationStatus,
        sanitize_environment,
    )
    from services.workspace_service import (
        WorkspaceCleanupResult,
        WorkspaceFileOperationResult,
        WorkspaceInfo,
        WorkspaceService,
        is_blocked_path,
    )


def __getattr__(name: str):
    if name in (
        "TaskRecord",
        "TaskService",
        "InvalidStateTransitionError",
        "VerificationAttemptRecord",
        "VerificationDiagnostics",
        "create_diagnostics_from_attempt",
        "TASK_LIFECYCLE_STATES",
        "VALID_TRANSITIONS",
    ):
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

        items = {
            "TaskRecord": TaskRecord,
            "TaskService": TaskService,
            "InvalidStateTransitionError": InvalidStateTransitionError,
            "VerificationAttemptRecord": VerificationAttemptRecord,
            "VerificationDiagnostics": VerificationDiagnostics,
            "create_diagnostics_from_attempt": create_diagnostics_from_attempt,
            "TASK_LIFECYCLE_STATES": TASK_LIFECYCLE_STATES,
            "VALID_TRANSITIONS": VALID_TRANSITIONS,
        }
        return items[name]

    if name in ("TaskLifecycleCoordinator", "RevisionResult", "DEFAULT_MAX_REVISIONS"):
        from services.lifecycle_service import (
            DEFAULT_MAX_REVISIONS,
            RevisionResult,
            TaskLifecycleCoordinator,
        )

        items = {
            "TaskLifecycleCoordinator": TaskLifecycleCoordinator,
            "RevisionResult": RevisionResult,
            "DEFAULT_MAX_REVISIONS": DEFAULT_MAX_REVISIONS,
        }
        return items[name]

    if name in (
        "WorkspaceCleanupResult",
        "WorkspaceFileOperationResult",
        "WorkspaceInfo",
        "WorkspaceService",
        "is_blocked_path",
    ):
        from services.workspace_service import (
            WorkspaceCleanupResult,
            WorkspaceFileOperationResult,
            WorkspaceInfo,
            WorkspaceService,
            is_blocked_path,
        )

        items = {
            "WorkspaceCleanupResult": WorkspaceCleanupResult,
            "WorkspaceFileOperationResult": WorkspaceFileOperationResult,
            "WorkspaceInfo": WorkspaceInfo,
            "WorkspaceService": WorkspaceService,
            "is_blocked_path": is_blocked_path,
        }
        return items[name]

    if name in (
        "CodeApplicationResult",
        "CodeApplicationService",
        "FileDiff",
        "generate_unified_diff",
    ):
        from services.code_application_service import (
            CodeApplicationResult,
            CodeApplicationService,
            FileDiff,
            generate_unified_diff,
        )

        items = {
            "CodeApplicationResult": CodeApplicationResult,
            "CodeApplicationService": CodeApplicationService,
            "FileDiff": FileDiff,
            "generate_unified_diff": generate_unified_diff,
        }
        return items[name]

    if name in (
        "VerificationService",
        "VerificationResult",
        "VerificationRequest",
        "VerificationStatus",
        "VerificationProfile",
        "BaseVerificationRunner",
        "DisabledSecurityRunner",
        "SubprocessSandboxRunner",
        "sanitize_environment",
    ):
        from services.verification_service import (
            BaseVerificationRunner,
            DisabledSecurityRunner,
            SubprocessSandboxRunner,
            VerificationProfile,
            VerificationRequest,
            VerificationResult,
            VerificationService,
            VerificationStatus,
            sanitize_environment,
        )

        items = {
            "VerificationService": VerificationService,
            "VerificationResult": VerificationResult,
            "VerificationRequest": VerificationRequest,
            "VerificationStatus": VerificationStatus,
            "VerificationProfile": VerificationProfile,
            "BaseVerificationRunner": BaseVerificationRunner,
            "DisabledSecurityRunner": DisabledSecurityRunner,
            "SubprocessSandboxRunner": SubprocessSandboxRunner,
            "sanitize_environment": sanitize_environment,
        }
        return items[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "TaskRecord",
    "TaskService",
    "WorkspaceService",
    "WorkspaceInfo",
    "WorkspaceFileOperationResult",
    "WorkspaceCleanupResult",
    "is_blocked_path",
    "CodeApplicationService",
    "CodeApplicationResult",
    "FileDiff",
    "generate_unified_diff",
    "VerificationService",
    "VerificationResult",
    "VerificationRequest",
    "VerificationStatus",
    "VerificationProfile",
    "BaseVerificationRunner",
    "DisabledSecurityRunner",
    "SubprocessSandboxRunner",
    "sanitize_environment",
    "TaskLifecycleCoordinator",
    "InvalidStateTransitionError",
    "VerificationAttemptRecord",
    "VerificationDiagnostics",
    "create_diagnostics_from_attempt",
    "RevisionResult",
    "DEFAULT_MAX_REVISIONS",
    "TASK_LIFECYCLE_STATES",
    "VALID_TRANSITIONS",
]
