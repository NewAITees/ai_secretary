"""Chat History Integration Tests

AISecretaryとChatHistoryRepositoryの統合テスト
"""

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock
from src.ai_secretary.secretary import AISecretary
from src.ai_secretary.config import Config, OllamaConfig
from src.chat_history.repository import ChatHistoryRepository


@pytest.fixture
def test_db_path(tmp_path):
    """テスト用の一時DBパス"""
    db_path = tmp_path / "test_integration.db"
    os.environ["AI_SECRETARY_DB_PATH"] = str(db_path)
    yield db_path
    # クリーンアップ
    if "AI_SECRETARY_DB_PATH" in os.environ:
        del os.environ["AI_SECRETARY_DB_PATH"]


@pytest.fixture
def mock_ollama_client():
    """モックOllamaClient"""
    client = Mock()
    client.model = "test-model"
    client.chat = Mock(return_value={
        "text": "テスト応答",
        "speakerUuid": "test-uuid",
        "styleId": 0,
        "speedScale": 1.0,
        "volumeScale": 1.0,
        "pitchScale": 0.0,
        "intonationScale": 1.0,
        "prePhonemeLength": 0.1,
        "postPhonemeLength": 0.1,
        "outputSamplingRate": 24000,
        "prosodyDetail": []
    })
    return client


@pytest.fixture
def secretary(test_db_path, mock_ollama_client):
    """AISecretaryインスタンス（履歴機能付き）"""
    config = Config(
        ollama=OllamaConfig(
            host="http://localhost:11434",
            model="test-model"
        ),
        coeiroink_api_url="http://localhost:50032",
        audio_output_dir="outputs/audio",
        system_prompt="テストシステムプロンプト",
        temperature=0.7,
        max_tokens=1000
    )

    # ChatHistoryRepositoryを明示的に初期化
    chat_repo = ChatHistoryRepository(db_path=test_db_path)

    secretary_instance = AISecretary(
        config=config,
        ollama_client=mock_ollama_client,
        coeiroink_client=None,  # COEIROINKは無効化
        audio_player=None,      # AudioPlayerは無効化
        bash_executor=None,     # BashExecutorは無効化
        chat_history_repo=chat_repo
    )

    return secretary_instance


def test_chat_saves_history_automatically(secretary, test_db_path):
    """会話が自動的に履歴に保存されることを確認"""
    # 最初の会話
    secretary.chat("こんにちは", return_json=True, play_audio=False)

    # 履歴が保存されているか確認
    repo = ChatHistoryRepository(db_path=test_db_path)
    session = repo.get_session(secretary.session_id)

    assert session is not None
    assert session.session_id == secretary.session_id
    assert session.title == "こんにちは"  # 最初のメッセージがタイトルになる
    assert len(session.messages) >= 2  # user + assistant（+ system prompts）


def test_multiple_chats_append_to_session(secretary, test_db_path):
    """複数回の会話が同じセッションに追記されることを確認"""
    # 複数回会話
    secretary.chat("最初の質問", return_json=True, play_audio=False)
    secretary.chat("2回目の質問", return_json=True, play_audio=False)
    secretary.chat("3回目の質問", return_json=True, play_audio=False)

    # 履歴確認
    repo = ChatHistoryRepository(db_path=test_db_path)
    session = repo.get_session(secretary.session_id)

    assert session is not None
    # user + assistant のペアが3組 + system prompts
    user_messages = [m for m in session.messages if m.get("role") == "user"]
    assistant_messages = [m for m in session.messages if m.get("role") == "assistant"]

    assert len(user_messages) == 3
    assert len(assistant_messages) == 3


def test_session_title_generated_from_first_message(secretary, test_db_path):
    """セッションタイトルが最初のメッセージから生成されることを確認"""
    first_message = "これは最初のメッセージです"
    secretary.chat(first_message, return_json=True, play_audio=False)

    repo = ChatHistoryRepository(db_path=test_db_path)
    session = repo.get_session(secretary.session_id)

    assert session is not None
    assert session.title == first_message


def test_long_message_truncated_in_title(secretary, test_db_path):
    """長いメッセージがタイトルで切り詰められることを確認"""
    long_message = "これは非常に長いメッセージです。" * 10  # 30文字を超える
    secretary.chat(long_message, return_json=True, play_audio=False)

    repo = ChatHistoryRepository(db_path=test_db_path)
    session = repo.get_session(secretary.session_id)

    assert session is not None
    assert len(session.title) <= 33  # 30文字 + "..."


def test_reset_conversation_creates_new_session(secretary, test_db_path):
    """会話リセット時に新しいセッションが作成されることを確認"""
    # 最初のセッション
    secretary.chat("最初のセッション", return_json=True, play_audio=False)
    first_session_id = secretary.session_id

    # 会話リセット
    secretary.reset_conversation()

    # 2回目のセッション
    secretary.chat("2回目のセッション", return_json=True, play_audio=False)
    second_session_id = secretary.session_id

    # セッションIDが異なることを確認
    assert first_session_id != second_session_id

    # 両方のセッションがDBに保存されている
    repo = ChatHistoryRepository(db_path=test_db_path)
    session1 = repo.get_session(first_session_id)
    session2 = repo.get_session(second_session_id)

    assert session1 is not None
    assert session2 is not None
    assert session1.title == "最初のセッション"
    assert session2.title == "2回目のセッション"


def test_load_session_restores_conversation(secretary, test_db_path):
    """セッション読み込みで会話が復元されることを確認"""
    # 最初のセッションで会話
    secretary.chat("過去の会話1", return_json=True, play_audio=False)
    secretary.chat("過去の会話2", return_json=True, play_audio=False)
    old_session_id = secretary.session_id

    # 会話リセット（新しいセッション）
    secretary.reset_conversation()

    # 過去のセッションを読み込み
    loaded = secretary.load_session(old_session_id)
    assert loaded is True

    # セッション情報が復元されている
    assert secretary.session_id == old_session_id
    assert secretary.session_title == "過去の会話1"

    # 会話履歴が復元されている
    user_messages = [m for m in secretary.conversation_history if m.get("role") == "user"]
    assert len(user_messages) == 2
    assert user_messages[0]["content"] == "過去の会話1"
    assert user_messages[1]["content"] == "過去の会話2"


def test_load_nonexistent_session_fails(secretary):
    """存在しないセッション読み込みが失敗することを確認"""
    loaded = secretary.load_session("nonexistent-session-id")
    assert loaded is False


def test_continue_conversation_after_load(secretary, test_db_path):
    """読み込んだセッションで会話を継続できることを確認"""
    # 最初のセッション
    secretary.chat("最初の質問", return_json=True, play_audio=False)
    old_session_id = secretary.session_id

    # リセット後に読み込み
    secretary.reset_conversation()
    secretary.load_session(old_session_id)

    # 会話を継続
    secretary.chat("続きの質問", return_json=True, play_audio=False)

    # DBから確認
    repo = ChatHistoryRepository(db_path=test_db_path)
    session = repo.get_session(old_session_id)

    user_messages = [m for m in session.messages if m.get("role") == "user"]
    assert len(user_messages) == 2
    assert user_messages[0]["content"] == "最初の質問"
    assert user_messages[1]["content"] == "続きの質問"


def test_session_list_shows_all_conversations(secretary, test_db_path):
    """複数セッションが一覧で取得できることを確認"""
    # 3つのセッションを作成
    for i in range(3):
        secretary.reset_conversation()
        secretary.chat(f"セッション{i+1}", return_json=True, play_audio=False)

    # 一覧取得
    repo = ChatHistoryRepository(db_path=test_db_path)
    sessions = repo.list_sessions(limit=10)

    assert len(sessions) == 3
    # 新しい順に並んでいることを確認
    assert sessions[0].title == "セッション3"
    assert sessions[1].title == "セッション2"
    assert sessions[2].title == "セッション1"


def test_search_sessions_by_keyword(secretary, test_db_path):
    """キーワードでセッション検索できることを確認"""
    # 異なる内容のセッションを作成
    secretary.chat("Pythonについて教えて", return_json=True, play_audio=False)
    secretary.reset_conversation()
    secretary.chat("Javaについて教えて", return_json=True, play_audio=False)

    # 検索
    repo = ChatHistoryRepository(db_path=test_db_path)
    results = repo.search_sessions("Python")

    assert len(results) == 1
    assert "Python" in results[0].title
