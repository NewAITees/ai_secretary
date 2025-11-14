"""Browser history data models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class BrowserHistoryEntry:
    """
    ブラウザ履歴エントリ

    Attributes:
        url: アクセスしたURL
        title: ページタイトル
        visit_time: 訪問日時
        visit_count: 訪問回数（Braveの累積カウント）
        transition_type: 遷移タイプ（0=リンク、1=手入力、等）
        source_browser: ブラウザ種別（brave, chrome, firefox等）
        brave_url_id: 元のurls.id（デバッグ用）
        brave_visit_id: 元のvisits.id（デバッグ用）
        id: データベースの主キー（保存後に設定）
        imported_at: インポート日時（保存後に設定）
    """

    url: str
    title: Optional[str]
    visit_time: datetime
    visit_count: int = 1
    transition_type: int = 0
    source_browser: str = "brave"
    brave_url_id: Optional[int] = None
    brave_visit_id: Optional[int] = None
    id: Optional[int] = None
    imported_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """辞書形式に変換（JSON出力用）"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "visit_time": self.visit_time.isoformat() if self.visit_time else None,
            "visit_count": self.visit_count,
            "transition_type": self.transition_type,
            "source_browser": self.source_browser,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
        }
