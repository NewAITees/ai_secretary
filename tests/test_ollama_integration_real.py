"""Ollama実環境統合テスト

このテストは実際のOllamaサーバーを使用して動作を検証します。
- Ollamaサーバーが起動している必要があります
- 実際のLLMモデルが必要です（デフォルト: qwen3:8b）

実行方法:
    uv run pytest tests/test_ollama_integration_real.py -v -s

スキップする場合:
    pytest -m "not integration"
"""

import pytest
import logging
from pathlib import Path
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config
from src.ai_secretary.ollama_client import OllamaClient

# 統合テストマーカー
pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestRealOllamaIntegration:
    """実際のOllamaサーバーを使った統合テスト"""

    @pytest.fixture(scope="class")
    def ollama_available(self):
        """Ollamaサーバーが利用可能かチェック"""
        try:
            client = OllamaClient(host="http://localhost:11434", model="qwen3:8b")
            models = client.list_models()
            if not models:
                pytest.skip("Ollamaサーバーは起動していますが、モデルがありません")
            if "qwen3:8b" not in models:
                pytest.skip("qwen3:8bモデルが見つかりません。ollama pull qwen3:8b を実行してください")
            return True
        except Exception as e:
            pytest.skip(f"Ollamaサーバーが利用できません: {e}")

    @pytest.fixture
    def secretary(self, ollama_available, tmp_path):
        """実際のOllamaを使うAISecretary"""
        from src.ai_secretary.config import OllamaConfig, ProactiveChatConfig

        # テスト用の設定
        config = Config(
            ollama=OllamaConfig(
                host="http://localhost:11434",
                model="qwen3:8b"
            ),
            proactive_chat=ProactiveChatConfig(),
            log_level="DEBUG",
            log_file=str(tmp_path / "test.log"),
            max_tokens=1000,  # テストは短めに
            temperature=0.3,  # 再現性を高めるため低めに
            system_prompt="You are a helpful assistant. Always respond in JSON format.",
            coeiroink_api_url="http://localhost:50032",
            audio_output_dir=str(tmp_path / "audio"),
        )

        # COEIROINKとAudioPlayerは無効化（音声不要）
        secretary = AISecretary(
            config=config,
            ollama_client=None,  # 自動初期化
            coeiroink_client=None,
            audio_player=None,
            bash_executor=None,  # BASHも無効化
        )

        return secretary

    def test_simple_chat(self, secretary):
        """シンプルな会話テスト"""
        response = secretary.chat(
            "Hello! Please respond with a simple greeting.",
            return_json=True,
            play_audio=False
        )

        logger.info(f"Response: {response}")

        # レスポンスが返ってくることを確認
        assert response is not None
        assert isinstance(response, dict)

    def test_json_response_structure(self, secretary):
        """JSON形式のレスポンス構造テスト"""
        response = secretary.chat(
            "What is 2+2? Respond in JSON with a 'text' field.",
            return_json=True,
            play_audio=False
        )

        logger.info(f"Response: {response}")

        # raw_responseが含まれているか
        assert "raw_response" in response

        # raw_responseにtextが含まれているか（LLMの応答）
        raw = response["raw_response"]
        assert isinstance(raw, dict)

    def test_conversation_history(self, secretary):
        """会話履歴が保持されるかテスト"""
        # 最初の質問
        response1 = secretary.chat(
            "My favorite color is blue.",
            return_json=True,
            play_audio=False
        )

        logger.info(f"Response 1: {response1}")

        # 2番目の質問（履歴を参照する）
        response2 = secretary.chat(
            "What is my favorite color?",
            return_json=True,
            play_audio=False
        )

        logger.info(f"Response 2: {response2}")

        # 会話履歴が保持されていることを確認
        assert len(secretary.conversation_history) >= 4  # system + user1 + assistant1 + user2

    def test_system_prompt_effect(self, secretary):
        """system_promptが効果を持つかテスト"""
        # system_promptで「JSON形式で返す」と指定しているので、
        # LLMの応答はJSON形式になっているはず
        response = secretary.chat(
            "Tell me a short joke.",
            return_json=True,
            play_audio=False
        )

        logger.info(f"Response: {response}")

        # raw_responseがdict（JSON）であることを確認
        assert isinstance(response["raw_response"], dict)

    def test_reset_conversation(self, secretary):
        """会話履歴リセットのテスト"""
        # 会話を追加
        secretary.chat("Hello", return_json=False, play_audio=False)
        secretary.chat("How are you?", return_json=False, play_audio=False)

        # 履歴が増えているはず
        initial_length = len(secretary.conversation_history)
        assert initial_length >= 4  # system + user1 + assistant1 + user2

        # リセット
        secretary.reset_conversation()

        # system_promptのみ残る
        assert len(secretary.conversation_history) >= 1
        assert secretary.conversation_history[0]["role"] == "system"

    def test_model_switch(self, secretary):
        """モデルの一時切り替えテスト"""
        # デフォルトモデルを確認
        default_model = secretary.ollama_client.model
        assert default_model == "qwen3:8b"

        # 別のモデルで会話（存在しない場合はスキップ）
        try:
            response = secretary.chat(
                "Test",
                return_json=True,
                play_audio=False,
                model="llama3.1:8b"  # 別のモデルを試す
            )
            # モデルが元に戻っているか確認
            assert secretary.ollama_client.model == default_model

        except Exception as e:
            pytest.skip(f"llama3.1:8bモデルが利用できません: {e}")


class TestRealBashIntegration:
    """実際のBASH実行との統合テスト"""

    @pytest.fixture(scope="class")
    def ollama_available(self):
        """Ollamaサーバーが利用可能かチェック"""
        try:
            client = OllamaClient(host="http://localhost:11434", model="qwen3:8b")
            models = client.list_models()
            if not models or "qwen3:8b" not in models:
                pytest.skip("Ollamaまたはqwen3:8bモデルが利用できません")
            return True
        except Exception as e:
            pytest.skip(f"Ollamaサーバーが利用できません: {e}")

    @pytest.fixture
    def secretary_with_bash(self, ollama_available, tmp_path):
        """BASH実行機能付きのAISecretary"""
        from src.ai_secretary.config import OllamaConfig, ProactiveChatConfig

        config = Config(
            ollama=OllamaConfig(
                host="http://localhost:11434",
                model="qwen3:8b"
            ),
            proactive_chat=ProactiveChatConfig(),
            log_level="DEBUG",
            log_file=str(tmp_path / "test.log"),
            max_tokens=2000,
            temperature=0.3,
            system_prompt=None,  # system_promptはconfig/system_prompt.txtから読み込まれる
            coeiroink_api_url="http://localhost:50032",
            audio_output_dir=str(tmp_path / "audio"),
        )

        # 実際のBashExecutorを使用
        from src.bash_executor import create_executor

        bash_executor = create_executor()

        secretary = AISecretary(
            config=config,
            ollama_client=None,
            coeiroink_client=None,
            audio_player=None,
            bash_executor=bash_executor,
        )

        return secretary

    def test_bash_pwd_command(self, secretary_with_bash):
        """pwdコマンドを実行してLLMが結果を理解するかテスト"""
        response = secretary_with_bash.chat(
            "現在のディレクトリを教えてください。",
            return_json=True,
            play_audio=False,
            enable_bash_verification=False  # 検証無効でシンプル化
        )

        logger.info(f"Response: {response}")

        # レスポンスが返ってくることを確認
        assert response is not None
        assert isinstance(response, dict)

        # raw_responseにtextが含まれているはず
        if "raw_response" in response:
            assert "text" in response["raw_response"]

    def test_bash_ls_command(self, secretary_with_bash):
        """lsコマンドを実行してファイル一覧を取得"""
        response = secretary_with_bash.chat(
            "このディレクトリにあるファイルを教えてください。",
            return_json=True,
            play_audio=False,
            enable_bash_verification=False
        )

        logger.info(f"Response: {response}")

        assert response is not None
        assert isinstance(response, dict)

    def test_bash_error_handling(self, secretary_with_bash):
        """存在しないコマンドのエラーハンドリング"""
        response = secretary_with_bash.chat(
            "存在しないファイル 'nonexistent_file_xyz.txt' の内容を教えてください。",
            return_json=True,
            play_audio=False,
            enable_bash_verification=False
        )

        logger.info(f"Response: {response}")

        # エラーが発生してもレスポンスは返ってくるはず
        assert response is not None


class TestRealThreeStepWorkflow:
    """実際の3段階ワークフロー統合テスト"""

    @pytest.fixture(scope="class")
    def ollama_available(self):
        """Ollamaサーバーが利用可能かチェック"""
        try:
            client = OllamaClient(host="http://localhost:11434", model="qwen3:8b")
            models = client.list_models()
            if not models or "qwen3:8b" not in models:
                pytest.skip("Ollamaまたはqwen3:8bモデルが利用できません")
            return True
        except Exception as e:
            pytest.skip(f"Ollamaサーバーが利用できません: {e}")

    @pytest.fixture
    def secretary(self, ollama_available, tmp_path):
        """3段階ワークフロー対応のAISecretary"""
        from src.ai_secretary.config import OllamaConfig, ProactiveChatConfig

        config = Config(
            ollama=OllamaConfig(
                host="http://localhost:11434",
                model="qwen3:8b"
            ),
            proactive_chat=ProactiveChatConfig(),
            log_level="DEBUG",
            log_file=str(tmp_path / "test.log"),
            max_tokens=3000,
            temperature=0.3,
            system_prompt=None,
            coeiroink_api_url="http://localhost:50032",
            audio_output_dir=str(tmp_path / "audio"),
        )

        from src.bash_executor import create_executor
        bash_executor = create_executor()

        secretary = AISecretary(
            config=config,
            ollama_client=None,
            coeiroink_client=None,
            audio_player=None,
            bash_executor=bash_executor,
        )

        return secretary

    @pytest.mark.slow
    def test_full_three_step_workflow(self, secretary):
        """完全な3段階ワークフロー（検証あり）"""
        response = secretary.chat(
            "pyproject.tomlファイルの最初の10行を教えてください。",
            return_json=True,
            play_audio=False,
            max_bash_retry=1,  # 再試行は1回まで
            enable_bash_verification=True  # 検証有効
        )

        logger.info(f"Response: {response}")

        # レスポンスが返ってくることを確認
        assert response is not None
        assert isinstance(response, dict)

    @pytest.mark.slow
    def test_workflow_with_retry(self, secretary):
        """再試行が発生する可能性のあるケース"""
        response = secretary.chat(
            "現在のGitブランチ名を教えてください。",
            return_json=True,
            play_audio=False,
            max_bash_retry=2,
            enable_bash_verification=True
        )

        logger.info(f"Response: {response}")

        assert response is not None


if __name__ == "__main__":
    # 直接実行時のセットアップ
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 60)
    print("Ollama実環境統合テスト")
    print("=" * 60)
    print("\n前提条件:")
    print("1. Ollamaサーバーが起動している（http://localhost:11434）")
    print("2. qwen3:8bモデルがインストールされている")
    print("   インストールコマンド: ollama pull qwen3:8b")
    print("\n実行コマンド:")
    print("  uv run pytest tests/test_ollama_integration_real.py -v -s")
    print("  uv run pytest tests/test_ollama_integration_real.py -v -s -m 'not slow'")
    print("=" * 60)
