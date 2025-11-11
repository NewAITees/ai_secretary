"""AISecretaryのBASH実行機能統合テスト"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config


class TestBashIntegration:
    """BASH実行機能の統合テスト"""

    @pytest.fixture
    def mock_bash_executor(self):
        """モックBashExecutorを作成"""
        mock = Mock()
        mock.root_dir = "/home/test"
        mock.validator = Mock()
        mock.validator.allowed_commands = {"ls", "pwd", "cat", "echo"}
        mock.execute.return_value = {
            "stdout": "/home/test\n",
            "stderr": "",
            "exit_code": "0",
            "cwd": "/home/test",
        }
        return mock

    @pytest.fixture
    def mock_config(self):
        """モックConfig"""
        config = Mock(spec=Config)
        config.ollama = Mock()
        config.ollama.host = "http://localhost:11434"
        config.ollama.model = "llama3.1:8b"
        config.temperature = 0.7
        config.max_tokens = 2000
        config.coeiroink_api_url = "http://localhost:50032"
        config.audio_output_dir = "outputs/audio"
        config.system_prompt = "You are a helpful AI secretary."
        return config

    @pytest.fixture
    def secretary_with_bash(self, mock_config, mock_bash_executor):
        """BashExecutor統合済みのAISecretaryを作成"""
        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient", side_effect=Exception("COEIROINK disabled for test")
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=mock_config,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
                bash_executor=mock_bash_executor,
            )
            return secretary

    def test_build_bash_instruction(self, secretary_with_bash):
        """_build_bash_instruction()がプロンプトを生成できるか"""
        instruction = secretary_with_bash._build_bash_instruction()

        assert instruction != ""
        assert "BASHコマンド実行機能" in instruction
        assert "bashActions" in instruction
        assert "pwd" in instruction or "ls" in instruction
        assert "制約事項" in instruction

    @patch("src.bash_executor.create_executor")
    def test_build_bash_instruction_without_executor(self, mock_create_executor, mock_config):
        """BashExecutor未初期化時は空文字を返すか"""
        # 自動初期化を無効化
        mock_create_executor.side_effect = Exception("Disabled")

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ):
            secretary = AISecretary(
                config=mock_config,
                ollama_client=Mock(),
                coeiroink_client=None,
            )
            # bash_executorがNoneであることを確認
            assert secretary.bash_executor is None
            instruction = secretary._build_bash_instruction()
            assert instruction == ""

    def test_process_bash_actions_success(self, secretary_with_bash, mock_bash_executor):
        """bashActionsの正常実行"""
        actions = [
            {"command": "pwd", "reason": "現在のディレクトリ確認"},
            {"command": "ls -la", "reason": "ファイル一覧取得"},
        ]

        mock_bash_executor.execute.side_effect = [
            {"stdout": "/home/test\n", "stderr": "", "exit_code": "0", "cwd": "/home/test"},
            {
                "stdout": "total 8\ndrwxr-xr-x 2 user user 4096 Jan 1 12:00 .\n",
                "stderr": "",
                "exit_code": "0",
                "cwd": "/home/test",
            },
        ]

        results = secretary_with_bash._process_bash_actions(actions)

        assert len(results) == 2
        assert results[0]["command"] == "pwd"
        assert results[0]["error"] is None
        assert results[0]["result"]["exit_code"] == "0"
        assert results[1]["command"] == "ls -la"
        assert results[1]["error"] is None

    def test_process_bash_actions_with_error(self, secretary_with_bash, mock_bash_executor):
        """bashActions実行時のエラーハンドリング"""
        actions = [{"command": "invalid_command", "reason": "存在しないコマンド"}]

        mock_bash_executor.execute.side_effect = Exception("Command not found")

        results = secretary_with_bash._process_bash_actions(actions)

        assert len(results) == 1
        assert results[0]["command"] == "invalid_command"
        assert results[0]["error"] == "Command not found"
        assert results[0]["result"] is None

    @patch("src.bash_executor.create_executor")
    def test_process_bash_actions_without_executor(self, mock_create_executor, mock_config):
        """BashExecutor未初期化時は空リストを返すか"""
        mock_create_executor.side_effect = Exception("Disabled")

        with patch("src.ai_secretary.secretary.OllamaClient"):
            secretary = AISecretary(
                config=mock_config, ollama_client=Mock(), coeiroink_client=None
            )
            assert secretary.bash_executor is None
            results = secretary._process_bash_actions([{"command": "pwd"}])
            assert results == []

    def test_format_bash_results_success(self, secretary_with_bash):
        """成功結果のフォーマット"""
        results = [
            {
                "command": "pwd",
                "reason": "ディレクトリ確認",
                "result": {
                    "stdout": "/home/test\n",
                    "stderr": "",
                    "exit_code": "0",
                    "cwd": "/home/test",
                },
                "error": None,
            }
        ]

        formatted = secretary_with_bash._format_bash_results(results)

        assert "✅" in formatted
        assert "pwd" in formatted
        assert "ディレクトリ確認" in formatted
        assert "/home/test" in formatted
        assert "終了コード: 0" in formatted

    def test_format_bash_results_error(self, secretary_with_bash):
        """エラー結果のフォーマット"""
        results = [
            {
                "command": "rm -rf /",
                "reason": "危険なコマンド",
                "result": None,
                "error": "SecurityError: Command not allowed",
            }
        ]

        formatted = secretary_with_bash._format_bash_results(results)

        assert "❌" in formatted
        assert "rm -rf /" in formatted
        assert "危険なコマンド" in formatted
        assert "SecurityError" in formatted

    def test_format_bash_results_long_output(self, secretary_with_bash):
        """長い出力の切り詰め"""
        long_output = "x" * 2000
        results = [
            {
                "command": "cat large_file.txt",
                "reason": "大きいファイル読み込み",
                "result": {
                    "stdout": long_output,
                    "stderr": "",
                    "exit_code": "0",
                    "cwd": "/home/test",
                },
                "error": None,
            }
        ]

        formatted = secretary_with_bash._format_bash_results(results)

        assert "省略" in formatted
        assert len(formatted) < len(long_output)

    @patch("src.ai_secretary.secretary.OllamaClient")
    def test_chat_with_bash_actions(
        self, mock_ollama_class, secretary_with_bash, mock_bash_executor
    ):
        """chat()メソッドでbashActionsを処理するか"""
        # OllamaのモックレスポンスにbashActionsを含める
        mock_ollama = Mock()
        mock_ollama.chat.return_value = {
            "text": "現在のディレクトリを確認しました。",
            "speakerUuid": "test-uuid",
            "styleId": 0,
            "speedScale": 1.0,
            "volumeScale": 1.0,
            "pitchScale": 0.0,
            "intonationScale": 1.0,
            "prePhonemeLength": 0.1,
            "postPhonemeLength": 0.1,
            "outputSamplingRate": 24000,
            "prosodyDetail": [],
            "bashActions": [{"command": "pwd", "reason": "現在のディレクトリ確認"}],
        }
        secretary_with_bash.ollama_client = mock_ollama

        mock_bash_executor.execute.return_value = {
            "stdout": "/home/test\n",
            "stderr": "",
            "exit_code": "0",
            "cwd": "/home/test",
        }

        # ステップ2のモックレスポンス（COEIROINKフィールドなし - coeiroink_client=Noneのため）
        step2_response = {"text": "現在のディレクトリは/home/testです"}
        verification_response = {"success": True, "reason": "OK", "suggestion": ""}
        mock_ollama.chat.side_effect = [
            mock_ollama.chat.return_value,  # 最初のchat() - Step 1
            step2_response,                  # ステップ2
            verification_response            # ステップ3（検証無効なので呼ばれない）
        ]

        # COEIROINKクライアントがNoneであることを確認（デバッグ）
        assert secretary_with_bash.coeiro_client is None, "coeiroink_client should be None"

        # chatを実行（検証無効でシンプル化）
        secretary_with_bash.chat("現在のディレクトリを教えて", play_audio=False, enable_bash_verification=False)

        # BashExecutorが呼ばれたか確認
        mock_bash_executor.execute.assert_called_once_with("pwd")

        # Step 2のシステムメッセージはクリーンアップされるため会話履歴には残らない
        # ただし、BashExecutorが呼ばれたことは既に確認済み
        # 最終的なアシスタント応答がStep 2のレスポンスであることを確認
        assistant_messages = [
            msg for msg in secretary_with_bash.conversation_history
            if msg.get("role") == "assistant"
        ]
        assert len(assistant_messages) >= 1, "No assistant messages found"
        # Step 2のレスポンスが最後のアシスタントメッセージになっている
        last_response = json.loads(assistant_messages[-1]["content"])
        assert "text" in last_response

    def test_bash_actions_invalid_format(self, secretary_with_bash):
        """不正な形式のbashActionsを無視するか"""
        # 文字列（配列でない）
        results = secretary_with_bash._process_bash_actions("invalid")
        assert results == []

        # 辞書のリストでない
        results = secretary_with_bash._process_bash_actions([1, 2, 3])
        assert results == []

        # commandキーがない
        results = secretary_with_bash._process_bash_actions([{"reason": "test"}])
        assert results == []


class TestBashExecutorInitialization:
    """BashExecutor初期化のテスト"""

    @patch("src.bash_executor.create_executor")
    @patch("src.ai_secretary.secretary.OllamaClient")
    def test_bash_executor_auto_initialization(self, mock_ollama, mock_create_executor):
        """bash_executor未指定時に自動初期化されるか"""
        mock_executor = Mock()
        mock_create_executor.return_value = mock_executor

        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="llama3.1:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Test"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        secretary = AISecretary(config=config, ollama_client=Mock(), coeiroink_client=None)

        mock_create_executor.assert_called_once()
        assert secretary.bash_executor is not None

    @patch("src.bash_executor.create_executor")
    @patch("src.ai_secretary.secretary.OllamaClient")
    def test_bash_executor_initialization_failure(self, mock_ollama, mock_create_executor):
        """BashExecutor初期化失敗時はNoneになるか"""
        mock_create_executor.side_effect = Exception("Initialization failed")

        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="llama3.1:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Test"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        secretary = AISecretary(config=config, ollama_client=Mock(), coeiroink_client=None)

        assert secretary.bash_executor is None



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

