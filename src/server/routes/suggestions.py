"""Suggestions API routes."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class Suggestion(BaseModel):
    """Suggestion schema"""

    id: int = Field(..., description="Suggestion ID")
    title: str = Field(..., description="Suggestion title")
    body: str = Field(..., description="Suggestion body")
    tags: List[str] = Field(default_factory=list, description="Tags")
    relevance_score: float = Field(..., description="Relevance score (0.0-1.0)")
    sources: List[str] = Field(default_factory=list, description="Source record IDs")
    presented_at: str = Field(..., description="Presented timestamp")
    feedback: int = Field(default=0, description="Feedback (-1: 👎, 0: 未評価, 1: 👍)")
    dismissed: bool = Field(default=False, description="Dismissed flag")


class SuggestionsResponse(BaseModel):
    """Suggestions list response"""

    suggestions: List[Suggestion] = Field(..., description="List of suggestions")


class FeedbackRequest(BaseModel):
    """Feedback request schema"""

    feedback: int = Field(..., description="Feedback value (-1, 0, 1)")


def get_db_path() -> Path:
    """Get database path"""
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "data" / "ai_secretary.db"


def register_suggestions_routes(app):
    """Register suggestions routes"""
    router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])

    @router.get("", response_model=SuggestionsResponse)
    def get_suggestions(
        limit: int = 10, dismissed: bool = False
    ) -> SuggestionsResponse:
        """
        Get suggestions

        Args:
            limit: Maximum number of suggestions to return
            dismissed: Include dismissed suggestions

        Returns:
            List of suggestions
        """
        db_path = get_db_path()

        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database not found")

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            if dismissed:
                query = "SELECT * FROM suggestions ORDER BY created_at DESC LIMIT ?"
            else:
                query = "SELECT * FROM suggestions WHERE dismissed = 0 ORDER BY created_at DESC LIMIT ?"

            rows = conn.execute(query, (limit,)).fetchall()

        suggestions = []
        for row in rows:
            import json

            suggestions.append(
                Suggestion(
                    id=row["id"],
                    title=row["title"],
                    body=row["body"],
                    tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
                    relevance_score=row["relevance_score"] or 0.0,
                    sources=json.loads(row["source_ids"]) if row["source_ids"] else [],
                    presented_at=row["presented_at"],
                    feedback=row["feedback"] or 0,
                    dismissed=bool(row["dismissed"]),
                )
            )

        return SuggestionsResponse(suggestions=suggestions)

    @router.post("/{suggestion_id}/feedback")
    def set_feedback(suggestion_id: int, request: FeedbackRequest):
        """
        Set feedback for a suggestion

        Args:
            suggestion_id: Suggestion ID
            request: Feedback request

        Returns:
            Success message
        """
        db_path = get_db_path()

        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database not found")

        if request.feedback not in [-1, 0, 1]:
            raise HTTPException(
                status_code=400, detail="Feedback must be -1, 0, or 1"
            )

        with sqlite3.connect(db_path) as conn:
            # Check if suggestion exists
            exists = conn.execute(
                "SELECT COUNT(*) FROM suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()[0]

            if not exists:
                raise HTTPException(status_code=404, detail="Suggestion not found")

            # Update feedback
            conn.execute(
                "UPDATE suggestions SET feedback = ? WHERE id = ?",
                (request.feedback, suggestion_id),
            )

        return {"ok": True, "message": "Feedback recorded"}

    @router.post("/{suggestion_id}/dismiss")
    def dismiss_suggestion(suggestion_id: int):
        """
        Dismiss a suggestion

        Args:
            suggestion_id: Suggestion ID

        Returns:
            Success message
        """
        db_path = get_db_path()

        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database not found")

        with sqlite3.connect(db_path) as conn:
            # Check if suggestion exists
            exists = conn.execute(
                "SELECT COUNT(*) FROM suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()[0]

            if not exists:
                raise HTTPException(status_code=404, detail="Suggestion not found")

            # Dismiss suggestion
            conn.execute(
                "UPDATE suggestions SET dismissed = 1 WHERE id = ?", (suggestion_id,)
            )

        return {"ok": True, "message": "Suggestion dismissed"}

    app.include_router(router)
