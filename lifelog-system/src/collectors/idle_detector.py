"""
Idle time detector for lifelog-system.

Linux互換実装（WSL2対応）
"""

import time
import logging


logger = logging.getLogger(__name__)


def get_idle_seconds_linux() -> float:
    """
    Linux環境でアイドル秒数を取得（モック実装）.

    WSL2では実際のユーザー入力情報を取得できないため、
    常に0を返す簡易実装。

    Windows環境では GetLastInputInfo を使用する予定。

    Returns:
        アイドル秒数
    """
    # TODO: 実際のLinux環境では xprintidle や XIDLETIME を使用
    # WSL2では取得不可のため、常にアクティブとみなす
    return 0.0


def get_idle_seconds() -> float:
    """
    最後のユーザー入力からの経過秒数を取得.

    Returns:
        アイドル秒数
    """
    # TODO: Windows環境の場合はWin32 API実装を呼び出す
    return get_idle_seconds_linux()
