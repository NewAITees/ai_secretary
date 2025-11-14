"""FastAPI application bootstrap."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import (
    register_bash_routes,
    register_chat_routes,
    register_proactive_routes,
    register_todo_routes,
    register_info_routes,
)

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="AI Secretary API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_chat_routes(app)
    register_proactive_routes(app)
    register_todo_routes(app)
    register_bash_routes(app)
    register_info_routes(app)

    return app


app = create_app()
