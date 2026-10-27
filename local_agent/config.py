"""Configuration settings for the Orbit AI Windows Local Agent service."""

import os
import secrets
from pathlib import Path
from typing import List

AGENT_VERSION = "1.0.0"
AGENT_NAME = "Orbit AI Windows Local Agent"

# Network binding
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001

HOST = os.getenv("ORBIT_AGENT_HOST", DEFAULT_HOST)
PORT = int(os.getenv("ORBIT_AGENT_PORT", str(DEFAULT_PORT)))

# Allowed CORS origins
ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]
custom_origins = os.getenv("ORBIT_ALLOWED_ORIGINS", "")
if custom_origins:
    ALLOWED_ORIGINS.extend([o.strip() for o in custom_origins.split(",") if o.strip()])

# Base data directory for local agent keys
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TOKEN_FILE = DATA_DIR / "local_agent_token.key"


def get_or_create_token() -> str:
    """Retrieves existing pairing token or generates and persists a new one."""
    env_token = os.getenv("ORBIT_AGENT_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if TOKEN_FILE.exists():
            saved_token = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if saved_token:
                return saved_token
    except Exception:
        pass

    new_token = secrets.token_hex(24)
    try:
        TOKEN_FILE.write_text(new_token, encoding="utf-8")
    except Exception:
        pass
    return new_token


TOKEN = get_or_create_token()

# Authorized project directories (defense-in-depth against arbitrary traversal)
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
AUTHORIZED_ROOTS: List[Path] = [
    WORKSPACE_ROOT.resolve(),
    Path.home().resolve(),
]

extra_roots = os.getenv("ORBIT_AUTHORIZED_DIRS", "")
if extra_roots:
    for r in extra_roots.split(os.pathsep):
        if r.strip():
            AUTHORIZED_ROOTS.append(Path(r.strip()).resolve())
