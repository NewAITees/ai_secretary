"""Chat History Repository Unit Tests

ChatHistoryRepositoryの単体テスト
"""

import pytest
import json
from pathlib import Path
from src.chat_history.repository import ChatHistoryRepository
from src.chat_history.models import ChatSession


@pytest.fixture
def test_db_path(tmp_path):
    """テスト用の一時DBパス"""
    import os
    db_path = tmp_path / "test_chat_history.db"
    os.environ["AI_SECRETARY_DB_PATH"] = str(db_path)
    yield db_path
    # クリーンアップ
    if "AI_SECRETARY_DB_PATH" in os.environ:
        del os.environ["AI_SECRETARY_DB_PATH"]


@pytest.fixture
def repo(test_db_path):
    """ChatHistoryRepositoryのインスタンス"""
    return ChatHistoryRepository(db_path=test_db_path)


def test_create_session(repo):
    """セッション作成のテスト"""
    messages = [
        {"role": "user", "content": "こんにちは"},
        {"role": "assistant", "content": "こんにちは！何かお手伝いできますか？"}
    ]

    session = repo.create_session(
        session_id="test-session-1",
        title="テストセッション",
        messages=messages
    )

    assert session.session_id == "test-session-1"
    assert session.title == "テストセッション"
    assert session.messages == messages
    assert session.created_at is not None
    assert session.updated_at is not None


def test_get_session(repo):
    """セッション取得のテスト"""
    messages = [{"role": "user", "content": "テスト"}]
    repo.create_session(
        session_id="test-session-2",
        title="取得テスト",
        messages=messages
    )

    session = repo.get_session("test-session-2")

    assert session is not None
    assert session.session_id == "test-session-2"
    assert session.title == "取得テスト"
    assert session.messages == messages


def test_get_nonexistent_session(repo):
    """存在しないセッションの取得テスト"""
    session = repo.get_session("nonexistent-id")
    assert session is None


def test_update_session(repo):
    """セッション更新のテスト"""
    initial_messages = [{"role": "user", "content": "最初"}]
    repo.create_session(
        session_id="test-session-3",
        title="更新テスト",
        messages=initial_messages
    )

    updated_messages = [
        {"role": "user", "content": "最初"},
        {"role": "assistant", "content": "返信"},
        {"role": "user", "content": "追加"}
    ]

    updated = repo.update_session(
        session_id="test-session-3",
        messages=updated_messages
    )

    assert updated is not None
    assert updated.session_id == "test-session-3"
    assert len(updated.messages) == 3
    assert updated.messages == updated_messages


def test_update_session_with_title(repo):
    """タイトル付きセッション更新のテスト"""
    repo.create_session(
        session_id="test-session-4",
        title="旧タイトル",
        messages=[{"role": "user", "content": "テスト"}]
    )

    updated = repo.update_session(
        session_id="test-session-4",
        messages=[{"role": "user", "content": "更新"}],
        title="新タイトル"
    )

    assert updated is not None
    assert updated.title == "新タイトル"
    assert updated.messages == [{"role": "user", "content": "更新"}]


def test_save_or_update_create(repo):
    """save_or_update（新規作成）のテスト"""
    messages = [{"role": "user", "content": "新規"}]
    session = repo.save_or_update(
        session_id="test-session-5",
        title="新規セッション",
        messages=messages
    )

    assert session.session_id == "test-session-5"
    assert session.title == "新規セッション"
    assert session.messages == messages


def test_save_or_update_update(repo):
    """save_or_update（更新）のテスト"""
    # 最初に作成
    repo.create_session(
        session_id="test-session-6",
        title="既存",
        messages=[{"role": "user", "content": "最初"}]
    )

    # 更新
    updated_messages = [
        {"role": "user", "content": "最初"},
        {"role": "assistant", "content": "追加"}
    ]
    session = repo.save_or_update(
        session_id="test-session-6",
        title="既存",
        messages=updated_messages
    )

    assert session.session_id == "test-session-6"
    assert len(session.messages) == 2


def test_list_sessions(repo):
    """セッション一覧取得のテスト"""
    import time

    # 複数のセッションを作成（時間差をつける）
    for i in range(3):
        repo.create_session(
            session_id=f"list-test-{i}",
            title=f"セッション{i}",
            messages=[{"role": "user", "content": f"メッセージ{i}"}]
        )
        time.sleep(0.01)  # わずかに時間差をつける

    sessions = repo.list_sessions(limit=10)

    assert len(sessions) == 3
    # 新しい順に並んでいることを確認
    assert sessions[0].session_id == "list-test-2"


def test_list_sessions_with_limit(repo):
    """セッション一覧取得（件数制限）のテスト"""
    for i in range(5):
        repo.create_session(
            session_id=f"limit-test-{i}",
            title=f"セッション{i}",
            messages=[{"role": "user", "content": f"メッセージ{i}"}]
        )

    sessions = repo.list_sessions(limit=3)
    assert len(sessions) == 3


def test_search_sessions_by_title(repo):
    """タイトル検索のテスト"""
    repo.create_session(
        session_id="search-1",
        title="Pythonの質問",
        messages=[{"role": "user", "content": "Pythonについて"}]
    )
    repo.create_session(
        session_id="search-2",
        title="Javaの質問",
        messages=[{"role": "user", "content": "Javaについて"}]
    )

    results = repo.search_sessions("Python")

    assert len(results) == 1
    assert results[0].session_id == "search-1"


def test_search_sessions_by_message_content(repo):
    """メッセージ内容検索のテスト"""
    repo.create_session(
        session_id="content-search-1",
        title="セッション1",
        messages=[{"role": "user", "content": "Dockerの使い方"}]
    )
    repo.create_session(
        session_id="content-search-2",
        title="セッション2",
        messages=[{"role": "user", "content": "uvのインストール"}]
    )

    results = repo.search_sessions("Docker")

    assert len(results) == 1
    assert results[0].session_id == "content-search-1"


def test_delete_session(repo):
    """セッション削除のテスト"""
    repo.create_session(
        session_id="delete-test",
        title="削除テスト",
        messages=[{"role": "user", "content": "削除予定"}]
    )

    # 削除
    deleted = repo.delete_session("delete-test")
    assert deleted is True

    # 削除後は取得できない
    session = repo.get_session("delete-test")
    assert session is None


def test_delete_nonexistent_session(repo):
    """存在しないセッション削除のテスト"""
    deleted = repo.delete_session("nonexistent")
    assert deleted is False


def test_chat_session_messages_property(repo):
    """ChatSession.messagesプロパティのテスト"""
    messages = [
        {"role": "user", "content": "テスト"},
        {"role": "assistant", "content": "応答"}
    ]

    session = repo.create_session(
        session_id="property-test",
        title="プロパティテスト",
        messages=messages
    )

    # messagesプロパティでパースされた結果を取得
    parsed_messages = session.messages

    assert isinstance(parsed_messages, list)
    assert len(parsed_messages) == 2
    assert parsed_messages == messages
