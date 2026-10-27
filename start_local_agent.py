#!/usr/bin/env python3
"""Startup script for the Orbit AI Windows Local Agent."""

import sys
from pathlib import Path

# Ensure project root is on sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from local_agent.server import run_server

if __name__ == "__main__":
    run_server()
