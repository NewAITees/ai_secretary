"""ProactivePromptManagerのテストコード"""

import tempfile
from pathlib import Path

import pytest

from src.ai_secretary.prompt_templates import ProactivePromptManager


def test_load_templates_from_file():
    """テンプレートファイルから正常に読み込めることを確認"""
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        template_file = template_dir / "test.txt"

        # テストデータ作成
        template_file.write_text(
            "テンプレート1: {current_time}\n"
            "テンプレート2: {current_time}\n"
            "# コメント行\n"
            "\n"  # 空行
            "テンプレート3: {current_time}\n",
            encoding="utf-8",
        )

        manager = ProactivePromptManager(template_dir)

        # 空行とコメントを除いた3つのテンプレートが読み込まれる
        assert len(manager.templates) == 3
        assert "テンプレート1: {current_time}" in manager.templates
        assert "テンプレート2: {current_time}" in manager.templates
        assert "テンプレート3: {current_time}" in manager.templates


def test_generate_prompt_with_variable_substitution():
    """変数置換が正常に行われることを確認"""
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        template_file = template_dir / "test.txt"
        template_file.write_text(
            "現在時刻は {current_time} です。\n", encoding="utf-8"
        )

        manager = ProactivePromptManager(template_dir)
        prompt = manager.generate_prompt()

        # 変数が置換されているか確認
        assert "{current_time}" not in prompt
        assert "現在時刻は" in prompt


def test_fallback_template_when_no_files():
    """テンプレートファイルがない場合のフォールバック動作"""
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        manager = ProactivePromptManager(template_dir)

        # フォールバックテンプレートが使用される
        assert len(manager.templates) == 1
        assert "何かお手伝いできることはありますか" in manager.templates[0]


def test_add_template_at_runtime():
    """実行時にテンプレートを追加できることを確認"""
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        manager = ProactivePromptManager(template_dir)

        initial_count = len(manager.templates)
        manager.add_template("新しいテンプレート: {current_time}")

        assert len(manager.templates) == initial_count + 1
        assert "新しいテンプレート: {current_time}" in manager.templates


def test_reload_templates():
    """テンプレートを再読み込みできることを確認"""
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir)
        template_file = template_dir / "test.txt"
        template_file.write_text("初期テンプレート\n", encoding="utf-8")

        manager = ProactivePromptManager(template_dir)
        assert len(manager.templates) == 1

        # ファイルを更新
        template_file.write_text(
            "初期テンプレート\n更新されたテンプレート\n", encoding="utf-8"
        )

        manager.reload_templates()
        assert len(manager.templates) == 2
