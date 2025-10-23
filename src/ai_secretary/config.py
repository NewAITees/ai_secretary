"""
設定管理モジュール

設計ドキュメント参照: doc/design/configuration.md
関連クラス:
  - secretary.AISecretary: この設定を使用するメインクラス
  - ollama_client.OllamaClient: Ollama API設定を使用
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """アプリケーション設定クラス"""

    # Ollama設定
    ollama_host: str = "http://localhost:11434"
    model_name: str = "qwen3:8b"

    # ログ設定
    log_level: str = "INFO"
    log_file: str = "logs/ai_secretary.log"

    # COEIROINK設定
    coeiroink_api_url: str = "http://localhost:50032"
    audio_output_dir: str = "outputs/audio"

    # AI生成設定
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む"""
        return cls(
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_name=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/ai_secretary.log"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            system_prompt=os.getenv("SYSTEM_PROMPT"),
            coeiroink_api_url=os.getenv("COEIROINK_API_URL", "http://localhost:50032"),
            audio_output_dir=os.getenv("AUDIO_OUTPUT_DIR", "outputs/audio"),
        )
