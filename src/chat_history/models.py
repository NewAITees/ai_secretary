"""Chat History Models

チャット履歴のデータモデル定義。

Design Reference: plan/P3_CHAT_HISTORY_PLAN_v2.md
Related Classes: ChatHistoryRepository (repository.py)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any
import json


@dataclass(slots=True)
class ChatSession:
    """チャットセッションの表現

    1セッション = 1つの会話スレッド
    会話履歴全体をmessages_jsonにJSON配列として保存
    """

    id: int
    session_id: str  # UUID形式
    title: str  # セッションのタイトル（最初のメッセージから生成）
    messages_json: str  # JSON文字列（[{"role": "user", "content": "..."}, ...]）
    created_at: str  # ISO8601形式
    updated_at: str  # ISO8601形式

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """メッセージ履歴をパースして返す

        Returns:
            メッセージ配列 [{"role": "user", "content": "..."}, ...]

        Raises:
            json.JSONDecodeError: 不正なJSON形式の場合
        """
        return json.loads(self.messages_json)

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """メッセージ履歴をJSON文字列に変換して設定

        Args:
            messages: メッセージ配列
        """
        self.messages_json = json.dumps(messages, ensure_ascii=False)
