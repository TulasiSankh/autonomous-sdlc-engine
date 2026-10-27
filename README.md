# Autonomous SDLC Engine

An extensible, modular multi-agent platform for orchestrating autonomous software development life cycle (SDLC) workflows—from planning and architecture through coding, testing, review, and verification.

---

## Architecture Overview

The system is structured with clear separation between API ingestion, orchestration logic, autonomous agent definitions, deterministic execution tools, and specialized skills.

```
autonomous-sdlc-engine/
├── .env.example          # Template for environment configuration (no secrets)
├── .gitignore            # Git ignore rules for Python, virtual environments, caches
├── requirements.txt      # Core application and testing dependencies
├── README.md             # Project documentation and quickstart guide
├── docs/                 # Architecture specifications and system design documents
│   └── architecture.md
├── api/                  # FastAPI application layer
│   ├── __init__.py
│   ├── main.py           # FastAPI entrypoint and router registration
│   └── routes/
│       ├── __init__.py
│       └── health.py     # Health-check endpoint (GET /health)
├── orchestrator/         # State machine and multi-agent coordination logic
│   └── __init__.py
├── agents/               # Autonomous agent personas (Planner, Coder, Reviewer, QA)
│   └── __init__.py
├── tools/                # Deterministic execution tools (Git, Filesystem, Terminal)
│   └── __init__.py
├── skills/               # Reusable procedural knowledge and SDLC playbooks
│   └── __init__.py
└── tests/                # Automated test suite
    ├── __init__.py
    └── test_health.py    # Automated test for GET /health endpoint
```

### Module Responsibilities

| Module | Responsibility |
| :--- | :--- |
| **`api/`** | Exposes REST endpoints to trigger, monitor, and interact with SDLC tasks. |
| **`orchestrator/`** | Coordinates agent sequencing, state transitions, context propagation, and artifact handoffs. |
| **`agents/`** | Houses specialized agents (e.g., Architect, Developer, Reviewer, Tester). |
| **`tools/`** | Provides sandboxed primitives for file editing, shell execution, testing, and git operations. |
| **`skills/`** | Encapsulates reusable multi-step engineering patterns and domain heuristics. |
| **`docs/`** | Architectural specifications, design rationales, and interface definitions. |
| **`tests/`** | Unit and integration test suites validating system components. |

For detailed design specifications, see [docs/architecture.md](docs/architecture.md).

---

## Getting Started

### 1. Prerequisites
- **Python 3.10+** (tested with Python 3.12)
- **pip** package manager

### 2. Set Up Virtual Environment

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### On Windows (Command Prompt):
```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy the example environment configuration:
```bash
# Windows PowerShell / CMD
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

---

## Running the Application

Start the FastAPI development server with Uvicorn:

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be accessible at:
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive OpenAPI Docs (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Verify Health Endpoint

Using `curl`:
```bash
curl http://127.0.0.1:8000/health
```

Expected JSON response:
```json
{
  "status": "healthy",
  "service": "autonomous-sdlc-engine",
  "version": "0.1.0"
}
```

---

## Windows Local Execution Agent

Orbit AI features a dedicated local Windows daemon that performs real operating system application inspection, controlled execution, and kernel process table verification.

- **Start Agent Daemon**: `python start_local_agent.py` or double-click `start_local_agent.bat`.
- **Local Port**: Binds strictly to `http://127.0.0.1:8001`.
- **Security**: Loopback-restricted, authenticated via `X-Orbit-Agent-Token`, with DNS rebinding protection and path confinement.
- **Detailed Documentation**: See [WINDOWS_LOCAL_AGENT_GUIDE.md](WINDOWS_LOCAL_AGENT_GUIDE.md).

---

## Running the Tests

Execute the automated test suite with `pytest`:

```bash
pytest
```

For verbose output with test names:
```bash
pytest -v
```

---

## Roadmap

This initial setup provides the foundation. Upcoming phases will implement:
1. **Orchestration State Machine**: Directed acyclic graph (DAG) runner for multi-step task execution.
2. **Tool Execution Primitives**: Safe filesystem, git, and execution sandboxes.
3. **Agent Definitions**: Specialized roles (Architect, Coder, Reviewer, Tester) with structured input/output schemas.
4. **Iterative Verification**: Automated test-and-repair loop before code delivery.
