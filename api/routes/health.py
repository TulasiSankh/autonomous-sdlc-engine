from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def health_check():
    """Returns the operational status of the SDLC engine service."""
    return {
        "status": "healthy",
        "service": "autonomous-sdlc-engine",
        "version": "0.1.0",
    }
