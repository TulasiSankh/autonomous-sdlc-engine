import asyncio
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes.health import router as health_router
from api.routes.local_agent import router as local_agent_router
from api.routes.planning import router as planning_router
from api.routes.tasks import router as tasks_router

# Set Windows Selector event loop policy to prevent WinError 64 IOCP socket drops
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

app = FastAPI(
    title="Autonomous SDLC Engine",
    description="Multi-Agent Autonomous Software Development Life Cycle Engine",
    version="0.1.0",
)

# Enable CORS for web dashboard and local frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_router)
app.include_router(local_agent_router)
app.include_router(planning_router, prefix="/tasks", tags=["Planning"])
app.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])


