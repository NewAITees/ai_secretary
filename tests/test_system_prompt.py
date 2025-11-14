"""system_prompt機能のテスト

このテストでは以下を検証します：
- system_promptの設定ファイルからの読み込み
- 会話履歴への適用
- カスタムプロンプトの動作
- 環境変数からの読み込み
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.ai_secretary.config import Config
from src.ai_secretary.secretary import AISecretary


class TestSystemPromptFromYAML:
    """YAMLファイルからのsystem_prompt読み込みテスト"""

    def test_load_system_prompt_from_file(self, tmp_path):
        """設定ファイルからsystem_promptを読み込めるか"""
        # テスト用のsystem_prompt.txtを作成
        prompt_content = "You are a helpful AI assistant specialized in Python development."
        prompt_file = tmp_path / "test_system_prompt.txt"
        prompt_file.write_text(prompt_content, encoding="utf-8")

        # テスト用のYAML設定を作成（相対パスではなく絶対パスを使用）
        config_content = f"""
ollama:
  host: http://localhost:11434
  model: qwen3:8b

proactive_chat:
  interval_seconds: 300
  max_queue_size: 10

log:
  level: INFO
  file: logs/test.log

coeiroink:
  api_url: http://localhost:50032
  audio_output_dir: outputs/audio

ai:
  max_tokens: 4096
  temperature: 0.7
  system_prompt_file: {str(prompt_file)}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content, encoding="utf-8")

        # Configを読み込む
        config = Config.from_yaml(config_file)

        assert config.system_prompt == prompt_content
        assert "Python development" in config.system_prompt

    def test_load_system_prompt_with_japanese_content(self, tmp_path):
        """日本語のsystem_promptを正しく読み込めるか"""
        # 日本語のsystem_prompt
        prompt_content = "あなたは親切で有能なAI秘書です。ユーザーの業務を支援します。"
        prompt_file = tmp_path / "japanese_prompt.txt"
        prompt_file.write_text(prompt_content, encoding="utf-8")

        config_content = f"""
ollama:
  host: http://localhost:11434
  model: qwen3:8b

ai:
  system_prompt_file: {str(prompt_file)}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content, encoding="utf-8")

        config = Config.from_yaml(config_file)

        assert config.system_prompt == prompt_content
        assert "AI秘書" in config.system_prompt

    def test_system_prompt_file_not_exists(self, tmp_path):
        """system_promptファイルが存在しない場合"""
        config_content = """
ollama:
  host: http://localhost:11434
  model: qwen3:8b

ai:
  system_prompt_file: non_existent_file.txt
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content, encoding="utf-8")

        config = Config.from_yaml(config_file)

        # ファイルが存在しない場合はNone
        assert config.system_prompt is None

    def test_system_prompt_file_not_specified(self, tmp_path):
        """system_prompt_fileが指定されていない場合"""
        config_content = """
ollama:
  host: http://localhost:11434
  model: qwen3:8b

ai:
  max_tokens: 4096
  temperature: 0.7
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content, encoding="utf-8")

        config = Config.from_yaml(config_file)

        assert config.system_prompt is None

    def test_load_actual_system_prompt(self):
        """実際のconfig/system_prompt.txtを読み込めるか"""
        # プロジェクトルートからの相対パスで読み込み
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config" / "app_config.yaml"

        if not config_path.exists():
            pytest.skip("app_config.yaml not found")

        config = Config.from_yaml(config_path)

        # system_promptが読み込まれているか確認
        if config.system_prompt:
            assert len(config.system_prompt) > 0
            # 実際のプロンプトには「AI秘書」が含まれているはず
            assert "AI秘書" in config.system_prompt or "assistant" in config.system_prompt.lower()


class TestSystemPromptFromEnv:
    """環境変数からのsystem_prompt読み込みテスト"""

    def test_load_system_prompt_from_env(self):
        """環境変数SYSTEM_PROMPTから読み込めるか"""
        test_prompt = "You are a test assistant."

        with patch.dict(os.environ, {"SYSTEM_PROMPT": test_prompt}):
            config = Config.from_env()
            assert config.system_prompt == test_prompt

    def test_system_prompt_env_not_set(self):
        """環境変数SYSTEM_PROMPTが設定されていない場合"""
        with patch.dict(os.environ, {}, clear=True):
            # 他の必須環境変数も削除される可能性があるため、必要なものを設定
            with patch.dict(
                os.environ,
                {
                    "OLLAMA_HOST": "http://localhost:11434",
                    "OLLAMA_MODEL": "qwen3:8b",
                },
            ):
                config = Config.from_env()
                assert config.system_prompt is None


class TestSystemPromptInSecretary:
    """AISecretaryでのsystem_prompt使用テスト"""

    @pytest.fixture
    def mock_config_with_prompt(self):
        """system_prompt付きのモックConfig"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "You are a helpful AI assistant."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"
        return config

    @pytest.fixture
    def mock_config_without_prompt(self):
        """system_promptなしのモックConfig"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = None
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"
        return config

    def test_system_prompt_added_to_conversation_history(self, mock_config_with_prompt):
        """system_promptが会話履歴に追加されるか"""
        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=mock_config_with_prompt,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
            )

            # 会話履歴の最初にsystem_promptが含まれているか確認
            system_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "system"
            ]

            # system_prompt + COEIROINK instruction (+ BASH instruction if enabled)
            assert len(system_messages) >= 1

            # 最初のシステムメッセージがsystem_prompt
            assert system_messages[0]["content"] == "You are a helpful AI assistant."

    def test_system_prompt_not_added_when_none(self, mock_config_without_prompt):
        """system_promptがNoneの場合は追加されないか"""
        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=mock_config_without_prompt,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
            )

            # system_promptがNoneの場合は追加されない
            system_messages = [
                msg
                for msg in secretary.conversation_history
                if msg.get("role") == "system"
                and msg.get("content") == mock_config_without_prompt.system_prompt
            ]

            assert len(system_messages) == 0

    def test_reset_conversation_preserves_system_prompt(self, mock_config_with_prompt):
        """会話履歴リセット時にsystem_promptは保持されるか"""
        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=mock_config_with_prompt,
                ollama_client=Mock(),
                coeiroink_client=None,
                audio_player=None,
            )

            # ユーザーメッセージを追加
            secretary.conversation_history.append({"role": "user", "content": "Hello"})
            secretary.conversation_history.append({"role": "assistant", "content": "Hi!"})

            # 会話履歴をリセット
            secretary.reset_conversation()

            # system_promptは残っているか
            system_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "system"
            ]

            assert len(system_messages) >= 1
            assert system_messages[0]["content"] == "You are a helpful AI assistant."

            # ユーザーメッセージとアシスタントメッセージは削除されているか
            user_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "user"
            ]
            assistant_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "assistant"
            ]

            assert len(user_messages) == 0
            assert len(assistant_messages) == 0

    def test_system_prompt_with_japanese_characters(self):
        """日本語のsystem_promptが正しく動作するか"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "あなたは親切で有能なAI秘書です。"
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ), patch("src.ai_secretary.secretary.AudioPlayer"):
            secretary = AISecretary(
                config=config, ollama_client=Mock(), coeiroink_client=None, audio_player=None
            )

            system_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "system"
            ]

            assert len(system_messages) >= 1
            assert "AI秘書" in system_messages[0]["content"]


class TestSystemPromptIntegration:
    """system_promptの統合テスト"""

    def test_system_prompt_affects_conversation(self, tmp_path):
        """system_promptが会話に影響を与えるか"""
        # カスタムsystem_promptを作成
        prompt_content = "You are a Python expert. Always provide code examples."
        prompt_file = tmp_path / "expert_prompt.txt"
        prompt_file.write_text(prompt_content, encoding="utf-8")

        config_content = f"""
ollama:
  host: http://localhost:11434
  model: qwen3:8b

ai:
  system_prompt_file: {str(prompt_file)}
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content, encoding="utf-8")

        config = Config.from_yaml(config_file)

        with patch("src.ai_secretary.secretary.OllamaClient") as mock_ollama_class, patch(
            "src.ai_secretary.secretary.COEIROINKClient", side_effect=Exception("Disabled")
        ), patch("src.ai_secretary.secretary.AudioPlayer"), patch(
            "src.bash_executor.create_executor", side_effect=Exception("Disabled")
        ):
            mock_ollama = Mock()
            mock_ollama_class.return_value = mock_ollama

            secretary = AISecretary(
                config=config, ollama_client=mock_ollama, coeiroink_client=None, audio_player=None
            )

            # Ollamaクライアントが受け取るメッセージにsystem_promptが含まれているか確認
            mock_ollama.chat.return_value = {
                "text": "Here is a code example...",
            }

            secretary.chat("How do I write a for loop?", play_audio=False)

            # Ollamaクライアントが呼ばれたか確認
            mock_ollama.chat.assert_called_once()

            # 渡されたメッセージを取得
            call_args = mock_ollama.chat.call_args
            messages = call_args[1]["messages"]

            # system_promptが含まれているか確認
            # 最初のメッセージがsystem_prompt
            assert messages[0]["role"] == "system"
            assert "Python expert" in messages[0]["content"]

    def test_multiple_system_messages_order(self):
        """複数のシステムメッセージが正しい順序で追加されるか"""
        config = Mock()
        config.ollama = Mock(host="http://localhost:11434", model="qwen3:8b")
        config.temperature = 0.7
        config.max_tokens = 2000
        config.system_prompt = "Initial system prompt."
        config.audio_output_dir = "outputs/audio"
        config.coeiroink_api_url = "http://localhost:50032"

        with patch("src.ai_secretary.secretary.OllamaClient"), patch(
            "src.ai_secretary.secretary.COEIROINKClient"
        ) as mock_coeiro_class, patch("src.ai_secretary.secretary.AudioPlayer"):
            # COEIROINKクライアントのモック
            mock_coeiro = Mock()
            mock_coeiro.speakers = {}  # 空のスピーカーリスト
            mock_coeiro_class.return_value = mock_coeiro

            secretary = AISecretary(
                config=config,
                ollama_client=Mock(),
                coeiroink_client=mock_coeiro,
                audio_player=None,
            )

            # システムメッセージの順序を確認
            # 1. system_prompt
            # 2. COEIROINK instruction (speakers が空なので空文字列)
            # 3. BASH instruction (bash_executorが有効な場合)

            system_messages = [
                msg for msg in secretary.conversation_history if msg.get("role") == "system"
            ]

            # 最低でもsystem_promptは含まれているはず
            assert len(system_messages) >= 1
            assert system_messages[0]["content"] == "Initial system prompt."
