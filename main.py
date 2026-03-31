"""
Application entry point for the chat backend.

This module is responsible for:
- creating the FastAPI application instance
- registering HTTP and WebSocket routers
- exposing lightweight global endpoints such as `/health`

Most business logic lives elsewhere:
- `routers/` for endpoint definitions
- `auth.py` and `services/` for authentication and service-layer logic
- `models/` for SQLAlchemy ORM models
- `schemas.py` for Pydantic request/response schemas
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth_routes import router as auth_router
from routers.message_routes import router as message_router
from routers.room_routes import router as room_router
from routers.ws_routes import router as ws_router


# Main FastAPI application instance used by the ASGI server.
app = FastAPI(title="Chat API", version="0.1.0")


# Allow local frontend development servers to access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register application routers by feature area.
app.include_router(auth_router)
app.include_router(room_router)
app.include_router(message_router)
app.include_router(ws_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Return a simple status response for health checks.

    This endpoint can be used by developers, containers, or deployment
    platforms to verify that the API process is running.
    """
    return {"status": "ok"}