"""複雑なシナリオのテスト."""

import pytest
from unittest.mock import Mock, patch
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestComplexScenarios:
    """複雑なシナリオのテスト"""

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

    def test_multiple_bash_commands_executed_sequentially(self, secretary_with_bash):
        """複数のBASHコマンドが順次実行されるか"""
        initial_response = {
            "text": "複数のコマンドを実行します",
            "bashActions": [
                {"command": "pwd", "reason": "ディレクトリ確認"},
                {"command": "ls", "reason": "ファイル一覧"},
                {"command": "cat README.md", "reason": "README確認"},
            ],
        }

        secretary_with_bash.bash_executor.execute.side_effect = [
            {"stdout": "/home/test\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
            {"stdout": "file1.py\nfile2.py\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
            {"stdout": "# README\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
        ]

        step2_response = {"text": "実行完了"}
        verification_response = {"success": True, "reason": "OK", "suggestion": ""}

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[step2_response, verification_response]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="プロジェクト情報を教えて",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        assert result == step2_response
        assert secretary_with_bash.bash_executor.execute.call_count == 3

    def test_bash_command_with_error_and_recovery(self, secretary_with_bash):
        """BASHコマンドエラーからの回復"""
        initial_response = {
            "text": "ファイルを読み込みます",
            "bashActions": [{"command": "cat non_existent.txt", "reason": "ファイル読み込み"}],
        }

        # 1回目: コマンドエラー
        secretary_with_bash.bash_executor.execute.side_effect = [
            Exception("File not found"),
            {"stdout": "Success\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
        ]

        step2_response_1 = {"text": "ファイルが見つかりませんでした"}
        verification_response_1 = {
            "success": False,
            "reason": "エラーを正しく処理していない",
            "suggestion": "別のファイルを試してください",
        }

        retry_response = {
            "text": "別のファイルを試します",
            "bashActions": [{"command": "cat README.md", "reason": "READMEを読み込み"}],
        }
        step2_response_2 = {"text": "READMEを読み込みました"}
        verification_response_2 = {"success": True, "reason": "OK", "suggestion": ""}

        secretary_with_bash.ollama_client.chat = Mock(
            side_effect=[
                step2_response_1,
                verification_response_1,
                retry_response,
                step2_response_2,
                verification_response_2,
            ]
        )

        result = secretary_with_bash._execute_bash_workflow(
            user_message="READMEを読んで",
            initial_response=initial_response,
            max_retry=2,
            enable_verification=True,
        )

        assert result == step2_response_2
