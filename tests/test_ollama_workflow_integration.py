"""3段階BASHワークフローの統合テスト."""

import pytest
from unittest.mock import Mock, patch
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestIntegratedThreeStepWorkflow:
    """3段階ワークフロー全体の統合テスト"""

    @pytest.fixture
    def secretary_with_bash(self):
        """フル機能のAISecretaryインスタンス"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "You are a helpful assistant."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        mock_bash_executor = Mock()
        mock_bash_executor.root_dir = "/home/test"
        mock_bash_executor.validator = Mock()
        mock_bash_executor.validator.allowed_commands = {"ls", "pwd", "cat", "echo"}
        mock_bash_executor.execute.return_value = {
            "stdout": "/home/test\n",
            "stderr": "",
            "exit_code": "0",
            "cwd": "/home/test",
        }

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=mock_bash_executor,
            )
            return secretary

    def test_full_workflow_success_first_attempt(self, secretary_with_bash):
        """3段階ワークフロー: 1回目で成功"""
        initial_response = {
            "text": "ディレクトリを確認します",
            "bashActions": [{"command": "pwd", "reason": "ディレクトリ確認"}],
        }

        step2_response = {"text": "現在のディレクトリは/home/testです"}
        verification_response = {"success": True, "reason": "完璧です", "suggestion": ""}

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[step2_response, verification_response]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="現在のディレクトリは？",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        assert result == step2_response
        assert secretary_with_bash.ollama_client.chat.call_count == 2  # Step2 + Step3

    def test_full_workflow_retry_once_then_success(self, secretary_with_bash):
        """3段階ワークフロー: 1回再試行して成功"""
        initial_response = {
            "text": "ファイルを確認します",
            "bashActions": [{"command": "ls", "reason": "ファイル一覧"}],
        }

        # 1回目失敗
        step2_response_1 = {"text": "ファイルはありません"}
        verification_response_1 = {
            "success": False,
            "reason": "実行結果を反映していない",
            "suggestion": "lsコマンドの出力を確認してください",
        }

        # 再試行で成功
        retry_step1_response = {
            "text": "再試行します",
            "bashActions": [{"command": "ls -la", "reason": "詳細表示"}],
        }
        step2_response_2 = {"text": "ファイル一覧を表示しました"}
        verification_response_2 = {"success": True, "reason": "OK", "suggestion": ""}

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[
                step2_response_1,
                verification_response_1,
                retry_step1_response,
                step2_response_2,
                verification_response_2,
            ]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="ファイル一覧を教えて",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        assert result == step2_response_2
        assert secretary_with_bash.ollama_client.chat.call_count == 5

    def test_full_workflow_max_retries_exceeded(self, secretary_with_bash):
        """3段階ワークフロー: 最大再試行回数超過"""
        initial_response = {
            "text": "コマンド実行",
            "bashActions": [{"command": "pwd", "reason": "テスト"}],
        }

        step2_response = {"text": "結果"}
        verification_response = {
            "success": False,
            "reason": "失敗",
            "suggestion": "再試行してください",
        }
        retry_response = {
            "text": "再試行",
            "bashActions": [{"command": "ls", "reason": "再試行"}],
        }

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[
                step2_response,
                verification_response,
                retry_response,
                step2_response,
                verification_response,
                retry_response,
                step2_response,
                verification_response,
            ]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="テスト",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        assert "申し訳ございません" in result["text"]
        assert "失敗しました" in result["text"]

    def test_full_workflow_verification_disabled(self, secretary_with_bash):
        """3段階ワークフロー: 検証無効の場合"""
        initial_response = {
            "text": "コマンド実行",
            "bashActions": [{"command": "pwd", "reason": "テスト"}],
        }

        step2_response = {"text": "結果を返します"}

        secretary_with_bash.ollama_client.chat = Mock(return_value=step2_response)

        result = secretary_with_bash._execute_bash_workflow(
            user_message="テスト",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=False,  # 検証無効
        )

        assert result == step2_response
        assert secretary_with_bash.ollama_client.chat.call_count == 1  # Step2のみ

    def test_full_workflow_no_bash_actions_in_retry(self, secretary_with_bash):
        """3段階ワークフロー: 再試行でbashActionsが生成されない場合"""
        initial_response = {
            "text": "コマンド実行",
            "bashActions": [{"command": "pwd", "reason": "テスト"}],
        }

        step2_response = {"text": "結果"}
        verification_response = {
            "success": False,
            "reason": "失敗",
            "suggestion": "再試行してください",
        }
        # 再試行時にbashActionsなし
        retry_response = {"text": "再試行できません"}

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[step2_response, verification_response, retry_response]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="テスト",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        # bashActionsがない場合は失敗として扱う
        assert "申し訳ございません" in result["text"]
