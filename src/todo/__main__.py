"""TODO CLI実行用エントリポイント

Usage:
    python -m src.todo.cli <command> [options]
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
