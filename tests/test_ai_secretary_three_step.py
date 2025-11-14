"""3段階BASHワークフローのテスト."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestThreeStepBashWorkflow:
    """3段階BASHワークフローのテスト"""

    @pytest.fixture
    def mock_bash_executor(self):
        """モックBashExecutorを作成"""
        mock = Mock()
        mock.root_dir = "/home/test"
        mock.validator = Mock()
        mock.validator.allowed_commands = {"ls", "pwd", "cat"}
        mock.execute.return_value = {
            "stdout": "file1.py\\nfile2.py\\n",
            "stderr": "",
            "exit_code": "0",
            "cwd": "/home/test",
        }
        return mock

    @pytest.fixture
    def secretary(self, mock_bash_executor):
        """AISecretaryインスタンス作成"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="llama3.1:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Test"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

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

    def test_execute_bash_workflow_no_bash_actions(self, secretary):
        """bashActionsがない場合は initial_response をそのまま返すか"""
        initial_response = {"text": "こんにちは", "bashActions": []}

        result = secretary._execute_bash_workflow(
            user_message="テスト",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True
        )

        assert result == initial_response

    def test_execute_bash_workflow_verification_disabled(self, secretary, mock_bash_executor):
        """検証無効時はステップ2の結果を返すか"""
        initial_response = {
            "text": "ファイルを確認します",
            "bashActions": [{"command": "ls", "reason": "ファイル一覧"}]
        }

        # ステップ2のモックレスポンス
        step2_mock_response = {"text": "ファイルはfile1.pyとfile2.pyです"}
        secretary.ollama_client.chat = Mock(return_value=step2_mock_response)

        result = secretary._execute_bash_workflow(
            user_message="ファイル一覧を教えて",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=False  # 検証無効
        )

        assert result == step2_mock_response
        mock_bash_executor.execute.assert_called_once_with("ls")

    def test_execute_bash_workflow_verification_success(self, secretary, mock_bash_executor):
        """検証成功時はステップ2の結果を返すか"""
        initial_response = {
            "text": "ファイルを確認します",
            "bashActions": [{"command": "ls", "reason": "ファイル一覧"}]
        }

        # ステップ2とステップ3のモックレスポンス
        step2_response = {"text": "ファイルはfile1.pyとfile2.pyです"}
        verification_response = {"success": True, "reason": "完璧です", "suggestion": ""}

        secretary.ollama_client.chat = Mock(side_effect=[step2_response, verification_response])

        result = secretary._execute_bash_workflow(
            user_message="ファイル一覧を教えて",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True
        )

        assert result == step2_response
        assert secretary.ollama_client.chat.call_count == 2  # ステップ2 + ステップ3

    def test_execute_bash_workflow_verification_failure_and_retry(
        self, secretary, mock_bash_executor
    ):
        """検証失敗時に再試行するか"""
        initial_response = {
            "text": "ファイルを確認します",
            "bashActions": [{"command": "ls", "reason": "ファイル一覧"}]
        }

        # 1回目: 検証失敗
        step2_response_1 = {"text": "ファイルが見つかりません"}
        verification_response_1 = {
            "success": False,
            "reason": "lsコマンドの結果を反映していない",
            "suggestion": "実行結果を確認してください"
        }

        # 2回目（再試行）: 検証成功
        retry_step1_response = {
            "text": "再試行します",
            "bashActions": [{"command": "ls -la", "reason": "詳細表示"}]
        }
        step2_response_2 = {"text": "ファイルはfile1.pyとfile2.pyです"}
        verification_response_2 = {"success": True, "reason": "OK", "suggestion": ""}

        secretary.ollama_client.chat = Mock(side_effect=[
            step2_response_1,        # 1回目ステップ2
            verification_response_1,  # 1回目ステップ3（失敗）
            retry_step1_response,     # 再試行ステップ1
            step2_response_2,         # 再試行ステップ2
            verification_response_2   # 再試行ステップ3（成功）
        ])

        result = secretary._execute_bash_workflow(
            user_message="ファイル一覧を教えて",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True
        )

        assert result == step2_response_2
        assert secretary.ollama_client.chat.call_count == 5
        assert mock_bash_executor.execute.call_count == 2  # 1回目 + 再試行

    def test_execute_bash_workflow_max_retry_exceeded(
        self, secretary, mock_bash_executor
    ):
        """最大再試行回数超過時のエラーハンドリング"""
        initial_response = {
            "text": "ファイルを確認します",
            "bashActions": [{"command": "ls", "reason": "ファイル一覧"}]
        }

        # すべて検証失敗
        step2_response = {"text": "結果"}
        verification_response = {
            "success": False,
            "reason": "失敗",
            "suggestion": "別のコマンドを試してください"
        }
        retry_response = {
            "text": "再試行",
            "bashActions": [{"command": "pwd", "reason": "テスト"}]
        }

        secretary.ollama_client.chat = Mock(side_effect=[
            step2_response, verification_response,  # 1回目失敗
            retry_response,
            step2_response, verification_response,  # 2回目失敗
            retry_response,
            step2_response, verification_response,  # 3回目失敗
        ])

        result = secretary._execute_bash_workflow(
            user_message="テスト",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True
        )

        # エラーメッセージが含まれているか
        assert "申し訳ございません" in result["text"]
        assert "失敗しました" in result["text"]
