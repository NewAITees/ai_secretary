"""Route registration helpers."""

from .bash import register_bash_routes
from .chat import register_chat_routes
from .proactive import register_proactive_routes
from .todo import register_todo_routes
from .info_collector import register_info_routes
from .tools import register_tool_routes

__all__ = [
    "register_bash_routes",
    "register_chat_routes",
    "register_proactive_routes",
    "register_todo_routes",
    "register_info_routes",
    "register_tool_routes",
]
