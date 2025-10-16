"""
AI秘書のメインモジュール

設計ドキュメント参照: doc/design/secretary.md
関連クラス:
  - config.Config: 設定管理
  - logger.setup_logger: ロギング設定
  - ollama_client.OllamaClient: Ollama API通信
"""

import logging
from typing import Dict, List, Optional

from .config import Config
from .ollama_client import OllamaClient


class AISecretary:
    """AI秘書のメインクラス"""

    def __init__(self, config: Optional[Config] = None):
        """
        初期化

        Args:
            config: 設定オブジェクト。Noneの場合は環境変数から読み込む
        """
        self.config = config or Config.from_env()
        self.logger = logging.getLogger(__name__)

        # Ollamaクライアントの初期化
        self.ollama_client = OllamaClient(
            host=self.config.ollama_host,
            model=self.config.model_name,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # 会話履歴の初期化
        self.conversation_history: List[Dict[str, str]] = []

        # システムプロンプトの設定
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )

    def chat(self, user_message: str, return_json: bool = False) -> Dict[str, Any]:
        """
        ユーザーメッセージに対して応答

        Args:
            user_message: ユーザーからのメッセージ
            return_json: JSON形式で応答を返すか（デフォルト: False、テキストのみ返す）

        Returns:
            AI秘書からの応答（辞書形式またはテキスト）
        """
        # ユーザーメッセージを履歴に追加
        self.conversation_history.append({"role": "user", "content": user_message})

        try:
            # Ollamaから応答を取得（デフォルトでJSON形式）
            response = self.ollama_client.chat(
                messages=self.conversation_history, stream=False, return_json=True
            )

            # アシスタントの応答を履歴に追加（JSON文字列として）
            import json

            response_str = json.dumps(response, ensure_ascii=False)
            self.conversation_history.append(
                {"role": "assistant", "content": response_str}
            )

            if return_json:
                return response
            else:
                # テキストのみを返す場合、responseから適切なフィールドを抽出
                if isinstance(response, dict) and "response" in response:
                    return response["response"]
                return str(response)

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return {"error": str(e)} if return_json else f"エラーが発生しました: {str(e)}"

    def reset_conversation(self):
        """会話履歴をリセット"""
        self.conversation_history.clear()
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )
        self.logger.info("会話履歴をリセットしました")

    def get_available_models(self) -> List[str]:
        """利用可能なモデルのリストを取得"""
        return self.ollama_client.list_models()

    def start(self):
        """秘書システムを起動"""
        self.logger.info("AI秘書システムを起動します")
        self.logger.info(f"使用モデル: {self.config.model_name}")
        self.logger.info(f"Ollamaホスト: {self.config.ollama_host}")

    def stop(self):
        """秘書システムを停止"""
        self.logger.info("AI秘書システムを停止します")
