import asyncio
import sys
import uvicorn
from api.main import app

def handle_exception(loop, context):
    exception = context.get("exception")
    # Suppress WinError 64 / socket closed on client disconnect
    if isinstance(exception, OSError) and getattr(exception, "winerror", None) == 64:
        return
    loop.default_exception_handler(context)

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    
    # Configure custom event loop with exception handler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(handle_exception)
    
    loop.run_until_complete(server.serve())
