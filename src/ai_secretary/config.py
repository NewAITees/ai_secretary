"""
設定管理モジュール

設計ドキュメント参照: doc/design/configuration.md
関連クラス:
  - secretary.AISecretary: この設定を使用するメインクラス
  - ollama_client.OllamaClient: Ollama API設定を使用
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class OllamaConfig:
    """Ollama API設定"""

    host: str = "http://localhost:11434"
    model: str = "qwen3:8b"


@dataclass
class ProactiveChatConfig:
    """能動的会話設定"""

    interval_seconds: int = 300  # デフォルト5分
    max_queue_size: int = 10


@dataclass
class Config:
    """アプリケーション設定クラス"""

    # Ollama設定
    ollama: OllamaConfig = None  # type: ignore

    # 能動的会話設定
    proactive_chat: ProactiveChatConfig = None  # type: ignore

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

    def __post_init__(self):
        """デフォルト値の初期化"""
        if self.ollama is None:
            self.ollama = OllamaConfig()
        if self.proactive_chat is None:
            self.proactive_chat = ProactiveChatConfig()

    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None) -> "Config":
        """YAMLファイルから設定を読み込む

        Args:
            config_path: 設定ファイルパス（省略時はconfig/app_config.yamlを使用）

        Returns:
            Config: 設定インスタンス
        """
        if config_path is None:
            # デフォルトのconfig/app_config.yamlを使用
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "app_config.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data: Dict[str, Any] = yaml.safe_load(f)

        # YAML構造から設定を抽出
        ollama_data = yaml_data.get("ollama", {})
        proactive_data = yaml_data.get("proactive_chat", {})
        log_data = yaml_data.get("log", {})
        coeiroink_data = yaml_data.get("coeiroink", {})
        ai_data = yaml_data.get("ai", {})

        # システムプロンプトをファイルから読み込む
        system_prompt = None
        system_prompt_file = ai_data.get("system_prompt_file")
        if system_prompt_file:
            prompt_path = config_path.parent.parent / system_prompt_file
            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    system_prompt = f.read().strip()

        return cls(
            ollama=OllamaConfig(
                host=ollama_data.get("host", "http://localhost:11434"),
                model=ollama_data.get("model", "qwen3:8b"),
            ),
            proactive_chat=ProactiveChatConfig(
                interval_seconds=proactive_data.get("interval_seconds", 300),
                max_queue_size=proactive_data.get("max_queue_size", 10),
            ),
            log_level=log_data.get("level", "INFO"),
            log_file=log_data.get("file", "logs/ai_secretary.log"),
            max_tokens=ai_data.get("max_tokens", 4096),
            temperature=ai_data.get("temperature", 0.7),
            system_prompt=system_prompt,
            coeiroink_api_url=coeiroink_data.get("api_url", "http://localhost:50032"),
            audio_output_dir=coeiroink_data.get("audio_output_dir", "outputs/audio"),
        )

    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む（後方互換性のため残す）"""
        return cls(
            ollama=OllamaConfig(
                host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
                model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
            ),
            proactive_chat=ProactiveChatConfig(
                interval_seconds=int(os.getenv("PROACTIVE_CHAT_INTERVAL", "300")),
                max_queue_size=int(os.getenv("PROACTIVE_CHAT_MAX_QUEUE", "10")),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/ai_secretary.log"),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            system_prompt=os.getenv("SYSTEM_PROMPT"),
            coeiroink_api_url=os.getenv("COEIROINK_API_URL", "http://localhost:50032"),
            audio_output_dir=os.getenv("AUDIO_OUTPUT_DIR", "outputs/audio"),
        )
