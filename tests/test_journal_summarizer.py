"""
JournalSummarizerのテスト
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.journal.summarizer import JournalSummarizer
from src.bash_executor import BashResult


class TestJournalSummarizer:
    """JournalSummarizerのテストクラス"""

    @pytest.fixture
    def mock_bash_executor(self):
        """BashExecutorのモック"""
        executor = MagicMock()
        return executor

    @pytest.fixture
    def mock_ollama_client(self):
        """OllamaClientのモック"""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_raw_data(self):
        """サンプルの構造化データ"""
        return {
            "date": "2025-11-14",
            "activities": [
                {
                    "occurred_at": "2025-11-14T10:30:00+09:00",
                    "title": "Pythonの勉強",
                    "details": "型ヒントについて学習",
                    "meta_json": '{"duration_minutes": 120, "energy_level": 4}',
                    "linked_todos": [
                        {"todo_id": 1, "todo_title": "Python学習", "relation": "progress"}
                    ],
                }
            ],
            "progress": {"entry_count": 1, "linked_todo_updates": 1},
            "todo_summary": [
                {
                    "todo_id": 1,
                    "todo_title": "Python学習",
                    "status": "doing",
                    "last_activity": "2025-11-14T10:30:00+09:00",
                }
            ],
        }

    def test_generate_daily_summary_without_llm(
        self, mock_bash_executor, sample_raw_data
    ):
        """LLMを使用しない日次サマリー生成"""
        # BASHスクリプト実行結果をモック
        bash_result = BashResult(
            success=True,
            stdout=json.dumps(sample_raw_data),
            stderr="",
            exit_code=0,
            parsed_json=sample_raw_data,
        )
        mock_bash_executor.execute.return_value = bash_result

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=None
        )

        result = summarizer.generate_daily_summary(
            date="2025-11-14", use_llm=False
        )

        # 検証
        assert result["date"] == "2025-11-14"
        assert "raw_data" in result
        assert result["raw_data"] == sample_raw_data
        assert result["statistics"]["entry_count"] == 1
        mock_bash_executor.execute.assert_called_once()

    def test_generate_daily_summary_with_llm(
        self, mock_bash_executor, mock_ollama_client, sample_raw_data
    ):
        """LLMを使用した日次サマリー生成"""
        # BASHスクリプト実行結果をモック
        bash_result = BashResult(
            success=True,
            stdout=json.dumps(sample_raw_data),
            stderr="",
            exit_code=0,
            parsed_json=sample_raw_data,
        )
        mock_bash_executor.execute.return_value = bash_result

        # LLM応答をモック
        llm_response = {
            "summary": "本日はPython学習を2時間実施しました。型ヒントについて深く学び、TODO #1の進捗を記録しました。",
            "highlights": [
                "Python型ヒントの学習（2時間）",
                "TODO #1「Python学習」の進捗あり",
            ],
            "suggestions": "明日も学習を継続し、実践的なコードを書いてみましょう。",
        }
        mock_ollama_client.chat.return_value = llm_response

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=mock_ollama_client
        )

        result = summarizer.generate_daily_summary(date="2025-11-14", use_llm=True)

        # 検証
        assert result["date"] == "2025-11-14"
        assert "summary" in result
        assert "Python学習を2時間実施" in result["summary"]
        assert "【ハイライト】" in result["summary"]
        assert "【次のアクション】" in result["summary"]
        assert result["statistics"]["entry_count"] == 1
        mock_bash_executor.execute.assert_called_once()
        mock_ollama_client.chat.assert_called_once()

    def test_generate_daily_summary_empty_data(self, mock_bash_executor):
        """空のデータの場合のサマリー生成"""
        empty_data = {
            "date": "2025-11-14",
            "activities": [],
            "progress": {"entry_count": 0, "linked_todo_updates": 0},
            "todo_summary": [],
        }

        bash_result = BashResult(
            success=True,
            stdout=json.dumps(empty_data),
            stderr="",
            exit_code=0,
            parsed_json=empty_data,
        )
        mock_bash_executor.execute.return_value = bash_result

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=None
        )

        result = summarizer.generate_daily_summary(date="2025-11-14", use_llm=False)

        # 検証
        assert result["date"] == "2025-11-14"
        assert "記録はありません" in result["summary"]
        assert result["statistics"]["entry_count"] == 0

    def test_generate_daily_summary_bash_failure(self, mock_bash_executor):
        """BASHスクリプト失敗時のエラーハンドリング"""
        bash_result = BashResult(
            success=False, stdout="", stderr="Database not found", exit_code=1
        )
        mock_bash_executor.execute.return_value = bash_result

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=None
        )

        result = summarizer.generate_daily_summary(date="2025-11-14")

        # 検証
        assert "error" in result
        assert "データ取得に失敗" in result["error"]
        assert "Database not found" in result["details"]

    def test_generate_daily_summary_llm_failure(
        self, mock_bash_executor, mock_ollama_client, sample_raw_data
    ):
        """LLM失敗時のフォールバック"""
        bash_result = BashResult(
            success=True,
            stdout=json.dumps(sample_raw_data),
            stderr="",
            exit_code=0,
            parsed_json=sample_raw_data,
        )
        mock_bash_executor.execute.return_value = bash_result

        # LLMが例外を投げる
        mock_ollama_client.chat.side_effect = Exception("LLM connection error")

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=mock_ollama_client
        )

        result = summarizer.generate_daily_summary(date="2025-11-14", use_llm=True)

        # 検証（フォールバックサマリーが生成される）
        assert result["date"] == "2025-11-14"
        assert "summary" in result
        assert "活動サマリー" in result["summary"]
        assert "error" in result
        assert "LLM生成失敗" in result["error"]

    def test_fallback_summary_format(self, sample_raw_data):
        """フォールバックサマリーのフォーマット検証"""
        summarizer = JournalSummarizer()

        fallback = summarizer._generate_fallback_summary(sample_raw_data)

        # 検証
        assert "【2025-11-14の活動サマリー】" in fallback
        assert "記録された活動: 1件" in fallback
        assert "TODO関連更新: 1件" in fallback
        assert "【活動一覧】" in fallback
        assert "Pythonの勉強" in fallback
        assert "(120分)" in fallback
        assert "TODO: #1 Python学習" in fallback

    def test_generate_daily_summary_default_date(self, mock_bash_executor):
        """日付未指定時は今日の日付を使用"""
        today = datetime.now().strftime("%Y-%m-%d")
        empty_data = {
            "date": today,
            "activities": [],
            "progress": {"entry_count": 0, "linked_todo_updates": 0},
            "todo_summary": [],
        }

        bash_result = BashResult(
            success=True,
            stdout=json.dumps(empty_data),
            stderr="",
            exit_code=0,
            parsed_json=empty_data,
        )
        mock_bash_executor.execute.return_value = bash_result

        summarizer = JournalSummarizer(
            bash_executor=mock_bash_executor, ollama_client=None
        )

        result = summarizer.generate_daily_summary(date=None, use_llm=False)

        # 検証
        assert result["date"] == today
        mock_bash_executor.execute.assert_called_with(
            "journal/generate_summary.sh", args=[today], parse_json=True
        )
