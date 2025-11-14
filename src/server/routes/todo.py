"""Todo endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

from fastapi import FastAPI, HTTPException

from src.todo import UNSET

from ..dependencies import get_todo_repository, serialize_todo
from ..schemas import TodoCreateRequest, TodoResponse, TodoUpdateRequest

logger = logging.getLogger(__name__)


def register_todo_routes(app: FastAPI) -> None:
    """Register todo CRUD endpoints."""

    @app.get("/api/todos", response_model=List[TodoResponse])
    async def list_todos() -> List[TodoResponse]:
        """List todos ordered by status/due date."""
        repo = get_todo_repository()
        try:
            todos = await asyncio.to_thread(repo.list)
            return [serialize_todo(todo) for todo in todos]
        except Exception as exc:
            logger.exception("Failed to list todos: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to list todos") from exc

    @app.post("/api/todos", response_model=TodoResponse)
    async def create_todo(request: TodoCreateRequest) -> TodoResponse:
        """Create a new todo."""
        repo = get_todo_repository()
        try:
            todo = await asyncio.to_thread(
                repo.create,
                request.title,
                request.description or "",
                request.due_date.isoformat() if request.due_date else None,
                request.status,
            )
            return serialize_todo(todo)
        except Exception as exc:
            logger.exception("Failed to create todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to create todo") from exc

    @app.patch("/api/todos/{todo_id}", response_model=TodoResponse)
    async def update_todo(todo_id: int, request: TodoUpdateRequest) -> TodoResponse:
        """Update an existing todo."""
        repo = get_todo_repository()
        try:
            payload = request.model_dump(exclude_unset=True)
            todo = await asyncio.to_thread(
                repo.update,
                todo_id,
                title=payload.get("title"),
                description=payload.get("description"),
                due_date=payload["due_date"].isoformat()
                if "due_date" in payload and payload["due_date"] is not None
                else (None if "due_date" in payload else UNSET),
                status=payload.get("status"),
            )
            if not todo:
                raise HTTPException(status_code=404, detail="Todo not found")
            return serialize_todo(todo)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to update todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to update todo") from exc

    @app.delete("/api/todos/{todo_id}")
    async def delete_todo(todo_id: int) -> Dict[str, bool]:
        """Delete a todo."""
        repo = get_todo_repository()
        try:
            deleted = await asyncio.to_thread(repo.delete, todo_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="Todo not found")
            return {"deleted": True}
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to delete todo: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to delete todo") from exc
