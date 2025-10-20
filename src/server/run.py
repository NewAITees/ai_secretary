"""CLI entry point for launching the FastAPI app with uvicorn."""

import uvicorn

from .app import app


def main() -> None:
    """Run the development server."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src"],
        factory=False,
    )


if __name__ == "__main__":
    main()
