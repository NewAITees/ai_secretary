"""
AISecretaryの日次サマリー機能統合テスト
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.ai_secretary.secretary import AISecretary


class TestAISecretarySummary:
    """AISecretaryの日次サマリー機能のテスト"""

    @pytest.fixture
    def mock_config(self):
        """Configのモック"""
        with patch("src.ai_secretary.secretary.Config") as mock:
            config = MagicMock()
            config.ollama.host = "http://localhost:11434"
            config.ollama.model = "llama3.1:8b"
            config.temperature = 0.7
            config.max_tokens = 4096
            config.coeiroink_api_url = "http://localhost:50032"
            config.audio_output_dir = "outputs/audio"
            config.system_prompt = "あなたはAI秘書です。"
            mock.from_yaml.return_value = config
            yield config

    @pytest.fixture
    def secretary_with_mocks(self, mock_config):
        """モック付きのAISecretary"""
        with patch("src.ai_secretary.secretary.COEIROINKClient"):
            with patch("src.ai_secretary.secretary.AudioPlayer"):
                secretary = AISecretary(config=mock_config)
                return secretary

    def test_get_daily_summary_without_llm(self, secretary_with_mocks):
        """LLMを使用しない日次サマリー取得"""
        with patch("src.journal.summarizer.BashScriptExecutor") as mock_executor_cls:
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor

            # BASHスクリプト実行結果をモック
            from src.bash_executor import BashResult

            sample_data = {
                "date": "2025-11-14",
                "activities": [
                    {
                        "occurred_at": "2025-11-14T10:30:00+09:00",
                        "title": "テスト活動",
                        "details": "統合テスト",
                        "meta_json": "{}",
                        "linked_todos": [],
                    }
                ],
                "progress": {"entry_count": 1, "linked_todo_updates": 0},
                "todo_summary": [],
            }

            bash_result = BashResult(
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                parsed_json=sample_data,
            )
            mock_executor.execute.return_value = bash_result

            result = secretary_with_mocks.get_daily_summary(
                date="2025-11-14", use_llm=False
            )

            # 検証
            assert result["date"] == "2025-11-14"
            assert "raw_data" in result
            assert result["raw_data"]["activities"][0]["title"] == "テスト活動"
            assert result["statistics"]["entry_count"] == 1

    def test_get_daily_summary_with_llm(self, secretary_with_mocks):
        """LLMを使用した日次サマリー取得"""
        with patch("src.journal.summarizer.BashScriptExecutor") as mock_executor_cls:
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor

            from src.bash_executor import BashResult

            sample_data = {
                "date": "2025-11-14",
                "activities": [
                    {
                        "occurred_at": "2025-11-14T10:30:00+09:00",
                        "title": "コードレビュー",
                        "details": "P5実装レビュー",
                        "meta_json": '{"duration_minutes": 60}',
                        "linked_todos": [],
                    }
                ],
                "progress": {"entry_count": 1, "linked_todo_updates": 0},
                "todo_summary": [],
            }

            bash_result = BashResult(
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                parsed_json=sample_data,
            )
            mock_executor.execute.return_value = bash_result

            # LLM応答をモック
            llm_response = {
                "summary": "本日はコードレビューを1時間実施しました。P5実装のレビューが完了しました。",
                "highlights": ["コードレビュー完了（1時間）"],
                "suggestions": "",
            }
            secretary_with_mocks.ollama_client.chat = MagicMock(
                return_value=llm_response
            )

            result = secretary_with_mocks.get_daily_summary(
                date="2025-11-14", use_llm=True
            )

            # 検証
            assert result["date"] == "2025-11-14"
            assert "summary" in result
            assert "コードレビューを1時間実施" in result["summary"]
            secretary_with_mocks.ollama_client.chat.assert_called_once()

    def test_get_daily_summary_default_date(self, secretary_with_mocks):
        """日付未指定時のサマリー取得"""
        today = datetime.now().strftime("%Y-%m-%d")

        with patch("src.journal.summarizer.BashScriptExecutor") as mock_executor_cls:
            mock_executor = MagicMock()
            mock_executor_cls.return_value = mock_executor

            from src.bash_executor import BashResult

            sample_data = {
                "date": today,
                "activities": [],
                "progress": {"entry_count": 0, "linked_todo_updates": 0},
                "todo_summary": [],
            }

            bash_result = BashResult(
                success=True,
                stdout="",
                stderr="",
                exit_code=0,
                parsed_json=sample_data,
            )
            mock_executor.execute.return_value = bash_result

            result = secretary_with_mocks.get_daily_summary(use_llm=False)

            # 検証
            assert result["date"] == today
            assert "記録はありません" in result["summary"]

    def test_get_daily_summary_error_handling(self, secretary_with_mocks):
        """サマリー取得エラー時のハンドリング"""
        with patch("src.journal.summarizer.BashScriptExecutor") as mock_executor_cls:
            # BashScriptExecutor初期化時に例外を投げる
            mock_executor_cls.side_effect = Exception("Executor initialization failed")

            result = secretary_with_mocks.get_daily_summary(date="2025-11-14")

            # 検証（エラーが適切にハンドリングされる）
            assert "error" in result
            assert "サマリー取得エラー" in result["error"]
            assert result["date"] == "2025-11-14"
