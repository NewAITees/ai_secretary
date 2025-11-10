"""
能動的会話用スケジューラーモジュール

設計ドキュメント参照: doc/design/proactive_chat.md
関連クラス:
  - secretary.AISecretary: AI秘書本体
  - prompt_templates.ProactivePromptManager: プロンプト管理
"""

import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from .prompt_templates import ProactivePromptManager


class ProactiveChatScheduler:
    """能動的会話を定期実行するスケジューラークラス"""

    def __init__(
        self,
        secretary: Any,  # AISecretaryの循環参照を避けるためAnyを使用
        prompt_manager: ProactivePromptManager,
        interval_seconds: int = 300,  # デフォルト5分
        max_queue_size: int = 10,
    ):
        """
        初期化

        Args:
            secretary: AISecretaryインスタンス
            prompt_manager: プロンプトテンプレート管理インスタンス
            interval_seconds: 実行間隔（秒）
            max_queue_size: メッセージキューの最大サイズ
        """
        self.secretary = secretary
        self.prompt_manager = prompt_manager
        self.interval_seconds = interval_seconds
        self.max_queue_size = max_queue_size
        self.logger = logging.getLogger(__name__)

        # 状態管理
        self._enabled = False
        self._running = False
        self._lock = threading.Lock()

        # メッセージキュー
        self._message_queue: Deque[Dict[str, Any]] = deque(maxlen=max_queue_size)

        # スレッド
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """スケジューラーを開始（バックグラウンドスレッド起動）"""
        with self._lock:
            if self._running:
                self.logger.warning("Scheduler is already running")
                return

            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            self.logger.info("Proactive chat scheduler started")

    def stop(self) -> None:
        """スケジューラーを停止"""
        with self._lock:
            if not self._running:
                self.logger.warning("Scheduler is not running")
                return

            self._running = False
            self.logger.info("Stopping proactive chat scheduler...")

        # スレッドの終了を待機
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            self.logger.info("Proactive chat scheduler stopped")

    def enable(self) -> None:
        """能動会話を有効化"""
        with self._lock:
            self._enabled = True
            self.logger.info("Proactive chat enabled")

    def disable(self) -> None:
        """能動会話を無効化"""
        with self._lock:
            self._enabled = False
            self.logger.info("Proactive chat disabled")

    def is_enabled(self) -> bool:
        """能動会話が有効かどうかを返す"""
        with self._lock:
            return self._enabled

    def get_status(self) -> Dict[str, Any]:
        """現在の状態を取得"""
        with self._lock:
            return {
                "enabled": self._enabled,
                "running": self._running,
                "interval_seconds": self.interval_seconds,
                "pending_count": len(self._message_queue),
            }

    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """保留中のメッセージを全て取得（取得後キューはクリア）"""
        with self._lock:
            messages = list(self._message_queue)
            self._message_queue.clear()
            self.logger.debug(f"Retrieved {len(messages)} pending messages")
            return messages

    def set_interval(self, interval_seconds: int) -> None:
        """実行間隔を変更"""
        if interval_seconds < 10:
            raise ValueError("Interval must be at least 10 seconds")

        with self._lock:
            self.interval_seconds = interval_seconds
            self.logger.info(f"Interval changed to {interval_seconds} seconds")

    def _run_loop(self) -> None:
        """
        メインループ（バックグラウンドスレッドで実行）

        interval_secondsごとに_run_taskを呼び出す
        """
        self.logger.info("Scheduler loop started")

        while True:
            with self._lock:
                if not self._running:
                    break

            # 次の実行までスリープ（1秒ごとに停止確認）
            for _ in range(self.interval_seconds):
                with self._lock:
                    if not self._running:
                        return
                time.sleep(1)

            # タスク実行
            self._run_task()

        self.logger.info("Scheduler loop exited")

    def _run_task(self) -> None:
        """
        定期実行タスク本体

        有効時のみプロンプト生成→AI会話実行→キューに追加
        """
        with self._lock:
            if not self._enabled:
                self.logger.debug("Proactive chat is disabled, skipping task")
                return

        try:
            # プロンプト生成
            prompt = self.prompt_manager.generate_prompt()
            self.logger.info(f"Running proactive chat task with prompt: {prompt}")

            # AI会話実行（secretaryのchatメソッドを呼び出し）
            result = self.secretary.chat(
                user_message=prompt,
                return_json=True,
                play_audio=True,
            )

            # メッセージをキューに追加
            message_data = {
                "text": result.get("voice_plan", {}).get("text", "応答を取得できませんでした"),
                "timestamp": time.time(),
                "details": result,
                "prompt": prompt,
            }

            with self._lock:
                self._message_queue.append(message_data)
                self.logger.info(
                    f"Proactive message added to queue (size: {len(self._message_queue)})"
                )

        except Exception as e:
            self.logger.error(f"Proactive chat task failed: {e}", exc_info=True)
            # エラー時もキューに追加（エラーメッセージとして）
            error_message = {
                "text": f"能動的会話の生成に失敗しました: {str(e)}",
                "timestamp": time.time(),
                "details": None,
                "error": True,
            }
            with self._lock:
                self._message_queue.append(error_message)
