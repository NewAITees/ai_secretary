"""Tool execution API routes."""

import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.ai_secretary.tool_executor import ToolExecutor


class ToolExecuteRequest(BaseModel):
    """Tool execution request schema"""

    tool: str = Field(..., description="Tool name to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if not provided)")
    role: str = Field(default="assistant", description="Role (assistant, system, admin)")


class ToolExecuteResponse(BaseModel):
    """Tool execution response schema"""

    ok: bool = Field(..., description="Execution success")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    parsed: Optional[Any] = Field(None, description="Parsed JSON output")
    error: Optional[str] = Field(None, description="Error message")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Execution metrics")


class ToolListResponse(BaseModel):
    """Tool list response schema"""

    tools: list[str] = Field(..., description="List of available tool names")


# Tool Executor singleton
_tool_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get or create ToolExecutor instance"""
    global _tool_executor
    if _tool_executor is None:
        project_root = Path(__file__).parent.parent.parent.parent
        tools_dir = project_root / "config" / "tools"
        capabilities_file = project_root / "config" / "tools" / "capabilities.json"
        audit_db_path = project_root / "data" / "ai_secretary.db"

        _tool_executor = ToolExecutor(
            tools_dir=tools_dir,
            capabilities_file=capabilities_file,
            audit_db_path=audit_db_path,
            project_root=project_root,
        )

    return _tool_executor


def register_tool_routes(app):
    """Register tool execution routes"""
    router = APIRouter(prefix="/api/tools", tags=["tools"])

    @router.post("/execute", response_model=ToolExecuteResponse)
    def execute_tool(request: ToolExecuteRequest) -> ToolExecuteResponse:
        """
        Execute a tool with given arguments

        Args:
            request: Tool execution request

        Returns:
            Execution result with stdout, stderr, and metrics
        """
        executor = get_tool_executor()

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        try:
            result = executor.execute(
                tool_name=request.tool,
                args=request.args,
                session_id=session_id,
                role=request.role,
            )

            return ToolExecuteResponse(**result)

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/list", response_model=ToolListResponse)
    def list_tools() -> ToolListResponse:
        """
        List all available tools

        Returns:
            List of tool names
        """
        executor = get_tool_executor()
        tools = executor.registry.list_tools()

        return ToolListResponse(tools=tools)

    app.include_router(router)
