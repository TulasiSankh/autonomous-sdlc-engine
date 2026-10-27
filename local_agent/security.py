"""Security and authentication utilities for the Orbit AI Local Agent."""

import logging
import os
import re
from pathlib import Path
from typing import Optional
from fastapi import Header, HTTPException, Request, status

from local_agent.config import AUTHORIZED_ROOTS, HOST, PORT, TOKEN

logger = logging.getLogger("local_agent.security")


def mask_sensitive_data(text: str) -> str:
    """Masks authorization tokens, API keys, and sensitive secrets in strings."""
    if not text:
        return ""
    # Mask pairing token if present
    if TOKEN and len(TOKEN) > 6:
        text = text.replace(TOKEN, f"{TOKEN[:3]}...{TOKEN[-3:]}")
    # Mask common API key patterns (OpenAI, Anthropic, generic hex/base64 tokens)
    text = re.sub(r"(sk-[a-zA-Z0-9_-]{20,})", r"sk-***MASKED***", text)
    text = re.sub(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", r"\1***MASKED***", text, flags=re.IGNORECASE)
    return text


def audit_log(action: str, details: str, client_ip: str = "127.0.0.1") -> None:
    """Records sanitized security audit events."""
    safe_details = mask_sensitive_data(details)
    logger.info(f"[AUDIT] action={action} client={client_ip} details={safe_details}")


def verify_host_header(request: Request) -> None:
    """Prevents DNS rebinding attacks by validating the HTTP Host header."""
    host_header = request.headers.get("host", "").split(":")[0].strip().lower()
    allowed_hosts = {"127.0.0.1", "localhost", "::1", "testserver"}
    if host_header not in allowed_hosts:
        audit_log("dns_rebinding_blocked", f"Invalid host header: {host_header}", request.client.host if request.client else "")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: DNS rebinding protection rejected Host header.",
        )


def verify_agent_token(
    x_orbit_agent_token: Optional[str] = Header(None, alias="X-Orbit-Agent-Token"),
    authorization: Optional[str] = Header(None),
) -> str:
    """Verifies that the request provides a valid pairing token."""
    provided_token: Optional[str] = None
    if x_orbit_agent_token:
        provided_token = x_orbit_agent_token.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        provided_token = authorization[7:].strip()

    if not provided_token or provided_token != TOKEN:
        audit_log("auth_failed", "Invalid or missing pairing token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Missing or invalid X-Orbit-Agent-Token pairing token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token


def validate_authorized_path(target_path_str: str) -> Path:
    """Validates that a filesystem path exists or is within an authorized root."""
    if not target_path_str or not target_path_str.strip():
        raise ValueError("Target path cannot be empty.")

    resolved = Path(target_path_str.strip()).resolve()

    # Disallow root drive deletion or traversal outside valid roots
    is_authorized = False
    for root in AUTHORIZED_ROOTS:
        try:
            resolved.relative_to(root)
            is_authorized = True
            break
        except ValueError:
            continue

    # Also permit valid Windows project drives if resolved and not system critical
    if not is_authorized and os.name == "nt":
        # Check that it's not Windows system directory
        system_root = Path(os.environ.get("SystemRoot", "C:\\Windows")).resolve()
        try:
            resolved.relative_to(system_root)
            raise ValueError(f"Access to Windows system directory '{resolved}' is prohibited.")
        except ValueError as err:
            if "prohibited" in str(err):
                raise
            # If not inside SystemRoot, allow directory/file on local drive if path exists or parent exists
            if resolved.exists() or resolved.parent.exists():
                is_authorized = True

    if not is_authorized:
        raise ValueError(
            f"Path '{resolved}' is outside authorized directories. "
            f"Authorized roots: {[str(r) for r in AUTHORIZED_ROOTS]}"
        )

    return resolved
