"""Route registration helpers."""

from .bash import register_bash_routes
from .chat import register_chat_routes
from .proactive import register_proactive_routes
from .todo import register_todo_routes

__all__ = [
    "register_bash_routes",
    "register_chat_routes",
    "register_proactive_routes",
    "register_todo_routes",
]
