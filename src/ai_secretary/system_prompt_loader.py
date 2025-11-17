"""
System Prompt Loader

BASH実行機能などのシステムプロンプトテンプレートを外部ファイルから読み込むユーティリティ。

関連クラス:
  - mixins.bash_workflow.BashWorkflowMixin: BASH実行機能
  - prompt_templates.ProactivePromptManager: 能動的会話用プロンプト（別用途）
"""

import logging
from pathlib import Path
from typing import Dict


class SystemPromptLoader:
    """システムプロンプトテンプレートのローダー（ファイル全体を読み込む）"""

    def __init__(self, base_dir: Path | None = None):
        """
        Args:
            base_dir: プロンプトファイルのベースディレクトリ
                      Noneの場合は config/system_prompts/ を使用
        """
        if base_dir is None:
            # プロジェクトルートを取得
            current = Path(__file__).resolve()
            project_root = current.parent.parent.parent
            base_dir = project_root / "config" / "system_prompts"

        self.base_dir = Path(base_dir)
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, str] = {}

    def load(self, prompt_path: str) -> str:
        """
        プロンプトテンプレートを読み込む（ファイル全体）

        Args:
            prompt_path: ベースディレクトリからの相対パス
                         例: "bash/layer0_bash_instruction.txt"

        Returns:
            プロンプトテンプレート文字列

        Raises:
            FileNotFoundError: ファイルが存在しない場合
        """
        # キャッシュチェック
        if prompt_path in self._cache:
            return self._cache[prompt_path]

        # ファイル読み込み
        file_path = self.base_dir / prompt_path
        if not file_path.exists():
            self.logger.error(f"Prompt file not found: {file_path}")
            raise FileNotFoundError(
                f"Prompt file not found: {file_path}\n"
                f"Base directory: {self.base_dir}\n"
                f"Relative path: {prompt_path}"
            )

        try:
            template = file_path.read_text(encoding="utf-8")
            self._cache[prompt_path] = template
            self.logger.debug(f"Loaded prompt template: {prompt_path}")
            return template
        except Exception as e:
            self.logger.error(f"Failed to read prompt file {file_path}: {e}")
            raise

    def format(self, prompt_path: str, **kwargs) -> str:
        """
        プロンプトテンプレートを読み込んで変数を置換

        Args:
            prompt_path: ベースディレクトリからの相対パス
            **kwargs: 置換する変数（{variable_name}形式）

        Returns:
            変数置換後のプロンプト文字列

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            KeyError: 必要な変数が提供されていない場合
        """
        template = self.load(prompt_path)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            self.logger.error(f"Missing template variable: {e} in {prompt_path}")
            raise

    def clear_cache(self):
        """キャッシュをクリア（開発時のリロード用）"""
        self._cache.clear()
        self.logger.debug("Prompt cache cleared")
