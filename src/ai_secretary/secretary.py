"""
AI秘書のメインモジュール

設計ドキュメント参照: doc/design/secretary.md
関連クラス:
  - config.Config: 設定管理
  - logger.setup_logger: ロギング設定
  - ollama_client.OllamaClient: Ollama API通信
"""

import json
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .mixins import BashWorkflowMixin, VoiceMixin
from .ollama_client import OllamaClient
from ..coeiroink_client import COEIROINKClient  # type: ignore

try:
    from ..audio_player import AudioPlayer  # type: ignore
except Exception:  # pragma: no cover - AudioPlayerを利用できない環境向け
    AudioPlayer = None  # type: ignore[assignment]

try:
    from ..bash_executor import CommandExecutor  # type: ignore
except Exception:  # pragma: no cover - BashExecutorを利用できない環境向け
    CommandExecutor = None  # type: ignore[assignment]

try:
    from ..chat_history import ChatHistoryRepository  # type: ignore
except Exception:  # pragma: no cover - ChatHistoryを利用できない環境向け
    ChatHistoryRepository = None  # type: ignore[assignment]


class AISecretary(VoiceMixin, BashWorkflowMixin):
    """AI秘書のメインクラス"""

    def __init__(
        self,
        config: Optional[Config] = None,
        ollama_client: Optional[OllamaClient] = None,
        coeiroink_client: Optional[COEIROINKClient] = None,
        audio_player: Optional["AudioPlayer"] = None,
        bash_executor: Optional["CommandExecutor"] = None,
        chat_history_repo: Optional["ChatHistoryRepository"] = None,
    ):
        """
        初期化

        Args:
            config: 設定オブジェクト。Noneの場合はYAMLファイルから読み込む
            ollama_client: 依存性注入用のOllamaクライアント
            coeiroink_client: 依存性注入用のCOEIROINKクライアント
            audio_player: 依存性注入用のAudioPlayer
            bash_executor: 依存性注入用のBashExecutor
            chat_history_repo: 依存性注入用のChatHistoryRepository
        """
        self.config = config or Config.from_yaml()
        self.logger = logging.getLogger(__name__)

        # Ollamaクライアントの初期化
        self.ollama_client = ollama_client or OllamaClient(
            host=self.config.ollama.host,
            model=self.config.ollama.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # COEIROINKクライアントとAudioPlayer
        self.coeiro_client: Optional[COEIROINKClient]
        if coeiroink_client is not None:
            self.coeiro_client = coeiroink_client
        else:
            try:
                self.coeiro_client = COEIROINKClient(
                    api_url=self.config.coeiroink_api_url
                )
            except Exception as e:  # pragma: no cover - 実行環境依存
                self.logger.error(f"COEIROINKクライアント初期化失敗: {e}")
                self.coeiro_client = None

        self.audio_player: Optional["AudioPlayer"] = audio_player
        if self.audio_player is None and AudioPlayer is not None:
            try:
                self.audio_player = AudioPlayer()
            except Exception as e:  # pragma: no cover - 実行環境依存
                self.logger.error(f"AudioPlayer初期化失敗: {e}")
                self.audio_player = None

        # 音声出力ディレクトリ
        self.audio_output_dir = Path(self.config.audio_output_dir)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)
        self.last_audio_path: Optional[Path] = None

        # 会話履歴の初期化
        self.conversation_history: List[Dict[str, str]] = []

        # システムプロンプトの設定
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )

        # COEIROINK利用ガイダンスを追加
        voice_instruction = self._build_voice_instruction()
        if voice_instruction:
            self.conversation_history.append(
                {"role": "system", "content": voice_instruction}
            )

        # BashExecutorの初期化
        self.bash_executor: Optional["CommandExecutor"] = bash_executor
        self.bash_approval_callback: Optional[Any] = None  # 承認コールバック
        if self.bash_executor is None:
            try:
                from ..bash_executor import create_executor, CommandValidator

                self.bash_executor = create_executor()
                # 承認コールバックを設定
                if self.bash_executor and self.bash_executor.validator:
                    self.bash_executor.validator.approval_callback = self._request_bash_approval
                self.logger.info("BashExecutor initialized successfully")
            except Exception as e:
                self.logger.warning(f"BashExecutor初期化失敗（機能は無効化されます）: {e}")
                self.bash_executor = None

        # BASH実行ガイダンスを追加
        bash_instruction = self._build_bash_instruction()
        if bash_instruction and self.bash_executor:
            self.conversation_history.append({"role": "system", "content": bash_instruction})

        # ChatHistoryRepositoryの初期化
        self.chat_history_repo: Optional["ChatHistoryRepository"] = chat_history_repo
        if self.chat_history_repo is None and ChatHistoryRepository is not None:
            try:
                self.chat_history_repo = ChatHistoryRepository()
                self.logger.info("ChatHistoryRepository initialized successfully")
            except Exception as e:
                self.logger.warning(f"ChatHistoryRepository初期化失敗（機能は無効化されます）: {e}")
                self.chat_history_repo = None

        # セッション管理
        self.session_id = str(uuid.uuid4())  # 新規セッションID
        self.session_title: Optional[str] = None  # セッションタイトル（最初のメッセージから生成）

    def chat(
        self,
        user_message: str,
        return_json: bool = False,
        play_audio: bool = True,
        model: Optional[str] = None,
        max_bash_retry: int = 2,
        enable_bash_verification: bool = True,
    ) -> Any:
        """
        ユーザーメッセージに対して応答（3段階BASHフロー対応）

        Args:
            user_message: ユーザーからのメッセージ
            return_json: JSON形式で応答を返すか（デフォルト: False、テキストのみ返す）
            play_audio: 生成した音声を即時再生するか
            model: 使用するモデル名（Noneの場合はデフォルトモデルを使用）
            max_bash_retry: BASH実行の最大再試行回数（デフォルト: 2）
            enable_bash_verification: BASH検証ステップを有効化（デフォルト: True）

        Returns:
            AI秘書からの応答（辞書形式またはテキスト）
        """
        # ユーザーメッセージを履歴に追加
        self.conversation_history.append({"role": "user", "content": user_message})

        # モデルを一時的に切り替える場合
        original_model = self.ollama_client.model
        if model is not None:
            self.ollama_client.model = model

        try:
            # Ollamaから応答を取得（デフォルトでJSON形式）
            raw_response = self.ollama_client.chat(
                messages=self.conversation_history, stream=False, return_json=True
            )

            # 3段階BASHフロー
            final_response = self._execute_bash_workflow(
                user_message=user_message,
                initial_response=raw_response,
                max_retry=max_bash_retry,
                enable_verification=enable_bash_verification
            )

            # アシスタントの応答を履歴に追加（JSON文字列として）
            response_str = json.dumps(final_response, ensure_ascii=False)
            self.conversation_history.append(
                {"role": "assistant", "content": response_str}
            )

            # チャット履歴を自動保存
            self._save_chat_history(user_message)

            voice_plan = None
            audio_path = None
            # COEIROINKクライアントが有効な場合のみ音声合成を試みる
            if self.coeiro_client is not None:
                voice_plan = self._extract_voice_plan(final_response)
                if voice_plan is not None:
                    audio_path = self._synthesize_and_optionally_play(
                        voice_plan, play_audio=play_audio
                    )

            result: Dict[str, Any] = {
                "voice_plan": voice_plan,
                "audio_path": str(audio_path) if audio_path else None,
                "played_audio": bool(audio_path and play_audio and self.audio_player),
            }

            if return_json:
                result["raw_response"] = raw_response
                return result
            if voice_plan:
                return voice_plan.get("text", json.dumps(voice_plan, ensure_ascii=False))
            return json.dumps(raw_response, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return {"error": str(e)} if return_json else f"エラーが発生しました: {str(e)}"
        finally:
            # モデルを元に戻す
            if model is not None:
                self.ollama_client.model = original_model

    def reset_conversation(self):
        """会話履歴をリセット（新規セッションとして扱う）"""
        self.conversation_history.clear()
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )
        # 新しいセッションIDを生成
        self.session_id = str(uuid.uuid4())
        self.session_title = None
        self.logger.info(f"会話履歴をリセットしました (new session: {self.session_id})")

    def get_available_models(self) -> List[str]:
        """利用可能なモデルのリストを取得"""
        return self.ollama_client.list_models()

    def start(self):
        """秘書システムを起動"""
        self.logger.info("AI秘書システムを起動します")
        self.logger.info(f"使用モデル: {self.config.ollama.model}")
        self.logger.info(f"Ollamaホスト: {self.config.ollama.host}")

    def stop(self):
        """秘書システムを停止"""
        self.logger.info("AI秘書システムを停止します")

    def load_session(self, session_id: str) -> bool:
        """
        過去のチャットセッションを読み込んで会話を再開

        Args:
            session_id: 読み込むセッションのID

        Returns:
            読み込み成功時True、失敗時False
        """
        if not self.chat_history_repo:
            self.logger.warning("ChatHistoryRepository未初期化のためセッション読み込みをスキップ")
            return False

        try:
            session = self.chat_history_repo.get_session(session_id)
            if not session:
                self.logger.warning(f"セッションが見つかりません: {session_id}")
                return False

            # セッション情報を復元
            self.session_id = session.session_id
            self.session_title = session.title
            self.conversation_history = session.messages

            self.logger.info(f"セッションを読み込みました: {session.title} ({session_id})")
            return True

        except Exception as e:
            self.logger.error(f"セッション読み込みに失敗: {e}")
            return False

    # =========================================================
    # 内部ユーティリティ
    # =========================================================

    def _save_chat_history(self, user_message: str) -> None:
        """
        チャット履歴を自動保存

        Args:
            user_message: ユーザーの最新メッセージ（タイトル生成用）
        """
        if not self.chat_history_repo:
            return

        # タイトル未設定なら最初のユーザーメッセージから生成
        if self.session_title is None:
            self.session_title = self._generate_title(user_message)

        try:
            self.chat_history_repo.save_or_update(
                session_id=self.session_id,
                title=self.session_title,
                messages=self.conversation_history
            )
            self.logger.debug(f"チャット履歴を保存しました: {self.session_title}")
        except Exception as e:
            self.logger.error(f"チャット履歴の保存に失敗: {e}")

    @staticmethod
    def _generate_title(user_message: str) -> str:
        """
        ユーザーメッセージからセッションタイトルを生成

        Args:
            user_message: ユーザーメッセージ

        Returns:
            タイトル（最大30文字）
        """
        # 改行や余分な空白を削除
        title = " ".join(user_message.split())
        # 最大30文字に制限
        if len(title) > 30:
            title = title[:30] + "..."
        return title

    def get_daily_summary(
        self, date: Optional[str] = None, use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        日次サマリーを取得

        Args:
            date: 対象日付（YYYY-MM-DD形式、Noneの場合は今日）
            use_llm: LLMを使用して自然言語サマリーを生成するか

        Returns:
            サマリー辞書
            - date: 対象日付
            - summary: 自然言語サマリー（use_llm=Trueの場合）
            - raw_data: 構造化データ
            - statistics: 統計情報

        Example:
            >>> secretary = AISecretary()
            >>> summary = secretary.get_daily_summary()
            >>> print(summary["summary"])
        """
        try:
            from ..journal import JournalSummarizer

            summarizer = JournalSummarizer(
                bash_executor=None,  # デフォルトを使用
                ollama_client=self.ollama_client,  # 既存のクライアントを共有
            )

            return summarizer.generate_daily_summary(date=date, use_llm=use_llm)

        except Exception as e:
            self.logger.error(f"日次サマリー取得に失敗: {e}")
            return {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "error": "サマリー取得エラー",
                "details": str(e),
            }
