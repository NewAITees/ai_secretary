"""
能動的会話用プロンプトテンプレート管理モジュール

設計ドキュメント参照: doc/design/proactive_chat.md
関連クラス:
  - scheduler.ProactiveChatScheduler: スケジューラー本体
"""

import logging
import random
from datetime import datetime
from pathlib import Path
from typing import List


class ProactivePromptManager:
    """能動的会話用のプロンプトテンプレート管理クラス"""

    def __init__(self, templates_dir: Path):
        """
        初期化

        Args:
            templates_dir: テンプレートファイルが格納されているディレクトリ
        """
        self.templates_dir = templates_dir
        self.logger = logging.getLogger(__name__)
        self.templates: List[str] = []
        self.load_templates()

    def load_templates(self) -> None:
        """
        テンプレートファイルを読み込む

        .txtファイルから行単位でテンプレートを読み込み、空行とコメント行（#で始まる）は無視する。
        """
        self.templates = []

        if not self.templates_dir.exists():
            self.logger.warning(f"Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.txt"):
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # 空行とコメント行をスキップ
                        if line and not line.startswith("#"):
                            self.templates.append(line)
                self.logger.info(f"Loaded {len(self.templates)} templates from {template_file}")
            except Exception as e:
                self.logger.error(f"Failed to load template file {template_file}: {e}")

        if not self.templates:
            # フォールバックテンプレート
            self.templates = [
                "現在時刻は {current_time} です。何かお手伝いできることはありますか？"
            ]
            self.logger.warning("No templates loaded, using fallback template")

    def generate_prompt(self) -> str:
        """
        ランダムに選択したテンプレートから変数を置換してプロンプトを生成

        Returns:
            変数が置換されたプロンプト文字列
        """
        if not self.templates:
            self.load_templates()

        template = random.choice(self.templates)
        now = datetime.now()

        # 変数置換
        try:
            prompt = template.format(
                current_time=now.strftime("%Y-%m-%d %H:%M:%S"),
                day_of_week=now.strftime("%A"),
                date=now.strftime("%Y-%m-%d"),
                time=now.strftime("%H:%M:%S"),
            )
        except KeyError as e:
            self.logger.error(f"Template variable error: {e}. Template: {template}")
            # エラー時はそのまま返す
            prompt = template

        self.logger.debug(f"Generated prompt: {prompt}")
        return prompt

    def add_template(self, template: str) -> None:
        """
        実行時に新しいテンプレートを追加

        Args:
            template: 追加するテンプレート文字列
        """
        self.templates.append(template)
        self.logger.info(f"Added new template: {template}")

    def reload_templates(self) -> None:
        """テンプレートファイルを再読み込み"""
        self.logger.info("Reloading templates...")
        self.load_templates()
