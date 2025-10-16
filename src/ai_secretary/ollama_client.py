"""
Ollama APIクライアントモジュール

設計ドキュメント参照: doc/design/ollama_integration.md
関連クラス:
  - config.Config: Ollama設定を提供
  - secretary.AISecretary: このクライアントを使用

注意: このクライアントは基本的にJSON形式でレスポンスを返します
"""

import json
import logging
from typing import Any, Dict, List, Optional

import ollama


class OllamaClient:
    """Ollama APIクライアント（JSON形式レスポンスが基本）"""

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        初期化

        Args:
            host: OllamaサーバーのURL
            model: 使用するモデル名
            temperature: 生成温度（0.0-1.0）
            max_tokens: 最大トークン数
        """
        self.host = host
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.logger = logging.getLogger(__name__)

        # Ollamaクライアントの設定
        self.client = ollama.Client(host=host)

    def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        return_json: bool = True,
    ) -> Dict[str, Any]:
        """
        チャット形式で会話（JSON形式がデフォルト）

        Args:
            messages: メッセージのリスト [{"role": "user", "content": "..."}]
            stream: ストリーミングレスポンスを使用するか
            return_json: JSON形式でレスポンスを返すか（デフォルト: True）

        Returns:
            JSON形式の辞書オブジェクト（return_json=Trueの場合）
            またはテキスト文字列（return_json=Falseの場合）
        """
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                stream=stream,
                format="json" if return_json else "",
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            if stream:
                # ストリーミングの場合は逐次処理が必要
                full_response = ""
                for chunk in response:
                    if "message" in chunk and "content" in chunk["message"]:
                        full_response += chunk["message"]["content"]

                if return_json:
                    return json.loads(full_response)
                return full_response
            else:
                content = response["message"]["content"]
                if return_json:
                    return json.loads(content)
                return content

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            raise ValueError(f"Ollamaからの応答がJSON形式ではありません: {e}")
        except Exception as e:
            self.logger.error(f"Ollama chat error: {e}")
            raise

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        stream: bool = False,
        return_json: bool = True,
    ) -> Dict[str, Any]:
        """
        プロンプトから生成（JSON形式がデフォルト）

        Args:
            prompt: 入力プロンプト
            system: システムプロンプト
            stream: ストリーミングレスポンスを使用するか
            return_json: JSON形式でレスポンスを返すか（デフォルト: True）

        Returns:
            JSON形式の辞書オブジェクト（return_json=Trueの場合）
            またはテキスト文字列（return_json=Falseの場合）
        """
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                system=system,
                stream=stream,
                format="json" if return_json else "",
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )

            if stream:
                # ストリーミングの場合は逐次処理が必要
                full_response = ""
                for chunk in response:
                    if "response" in chunk:
                        full_response += chunk["response"]

                if return_json:
                    return json.loads(full_response)
                return full_response
            else:
                content = response["response"]
                if return_json:
                    return json.loads(content)
                return content

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {e}")
            raise ValueError(f"Ollamaからの応答がJSON形式ではありません: {e}")
        except Exception as e:
            self.logger.error(f"Ollama generate error: {e}")
            raise

    def list_models(self) -> List[str]:
        """
        利用可能なモデルのリストを取得

        Returns:
            モデル名のリスト
        """
        try:
            models = self.client.list()
            return [model["name"] for model in models["models"]]
        except Exception as e:
            self.logger.error(f"Failed to list models: {e}")
            return []
