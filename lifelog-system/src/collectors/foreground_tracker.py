"""
Foreground window tracker for lifelog-system.

Linux互換実装（WSL2対応）
Windows環境では将来的にWin32 APIを使用
"""

import psutil
import logging
from functools import lru_cache
from typing import Optional

from ..utils.privacy import stable_hash, extract_domain_if_browser


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1024)
def pid_to_app_info(pid: int) -> dict[str, str]:
    """
    PID → アプリ情報の変換（LRUキャッシュで高速化）.

    Args:
        pid: プロセスID

    Returns:
        アプリ情報
    """
    try:
        proc = psutil.Process(pid)
        exe_path = proc.exe()
        return {
            "process_name": proc.name(),
            "process_path": exe_path,
            "process_path_hash": stable_hash(exe_path),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return {"process_name": "Unknown", "process_path": "", "process_path_hash": ""}


def get_active_window_info_linux() -> Optional[dict[str, str]]:
    """
    Linux環境でアクティブウィンドウ情報を取得（モック実装）.

    WSL2ではウィンドウ情報を取得できないため、
    実行中のプロセスから推定する簡易実装。

    Returns:
        ウィンドウ情報（取得できない場合はNone）
    """
    try:
        # 簡易実装: CPU使用率が高いプロセスを「アクティブ」と仮定
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not processes:
            return None

        # CPU使用率でソート
        processes.sort(key=lambda p: p.get("cpu_percent", 0.0), reverse=True)

        # 最もアクティブなプロセス
        active_proc = processes[0]
        pid = active_proc["pid"]
        app_info = pid_to_app_info(pid)

        # 簡易的なタイトル（プロセス名を使用）
        window_title = app_info["process_name"]

        return {
            "pid": pid,
            "window_title": window_title,
            "window_hash": stable_hash(window_title),
            "domain": extract_domain_if_browser(window_title, app_info["process_name"]),
            **app_info,
        }

    except Exception as e:
        logger.error(f"Failed to get active window info: {e}")
        return None


def get_foreground_info() -> Optional[dict[str, str]]:
    """
    現在のフォアグラウンド情報を取得.

    環境に応じて適切な実装を呼び出す。

    Returns:
        フォアグラウンド情報
    """
    # TODO: Windows環境の場合はWin32 API実装を呼び出す
    return get_active_window_info_linux()
