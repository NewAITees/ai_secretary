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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .ollama_client import OllamaClient
from ..coeiroink_client import COEIROINKClient, VoiceParameters, Speaker  # type: ignore

try:
    from ..audio_player import AudioPlayer  # type: ignore
except Exception:  # pragma: no cover - AudioPlayerを利用できない環境向け
    AudioPlayer = None  # type: ignore[assignment]


class AISecretary:
    """AI秘書のメインクラス"""

    def __init__(
        self,
        config: Optional[Config] = None,
        ollama_client: Optional[OllamaClient] = None,
        coeiroink_client: Optional[COEIROINKClient] = None,
        audio_player: Optional["AudioPlayer"] = None,
    ):
        """
        初期化

        Args:
            config: 設定オブジェクト。Noneの場合は環境変数から読み込む
            ollama_client: 依存性注入用のOllamaクライアント
            coeiroink_client: 依存性注入用のCOEIROINKクライアント
            audio_player: 依存性注入用のAudioPlayer
        """
        self.config = config or Config.from_env()
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

    def chat(
        self,
        user_message: str,
        return_json: bool = False,
        play_audio: bool = True,
        model: Optional[str] = None,
    ) -> Any:
        """
        ユーザーメッセージに対して応答

        Args:
            user_message: ユーザーからのメッセージ
            return_json: JSON形式で応答を返すか（デフォルト: False、テキストのみ返す）
            play_audio: 生成した音声を即時再生するか
            model: 使用するモデル名（Noneの場合はデフォルトモデルを使用）

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

            # アシスタントの応答を履歴に追加（JSON文字列として）
            response_str = json.dumps(raw_response, ensure_ascii=False)
            self.conversation_history.append(
                {"role": "assistant", "content": response_str}
            )

            voice_plan = self._extract_voice_plan(raw_response)
            audio_path = None
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
        self.logger.info(f"使用モデル: {self.config.ollama.model}")
        self.logger.info(f"Ollamaホスト: {self.config.ollama.host}")

    def stop(self):
        """秘書システムを停止"""
        self.logger.info("AI秘書システムを停止します")

    # =========================================================
    # 内部ユーティリティ
    # =========================================================

    def _build_voice_instruction(self) -> str:
        """COEIROINK利用のためのプロンプトを生成"""
        if not self.coeiro_client or not self.coeiro_client.speakers:
            return ""

        speaker_lines = []
        for speaker in sorted(
            self.coeiro_client.speakers.values(), key=lambda s: s.speaker_name
        ):
            style_descriptions = ", ".join(
                f"{style['styleName']} (styleId={style['styleId']})"
                for style in speaker.styles
            )
            speaker_lines.append(
                f"- speakerName: {speaker.speaker_name}, speakerUuid: {speaker.speaker_uuid}, styles: {style_descriptions}"
            )

        speaker_block = "\n".join(speaker_lines)
        return (
            "You are a response planner that prepares JSON payloads for the COEIROINK "
            "voice synthesis API. Follow these rules strictly:\n"
            "1. Answer ONLY with valid JSON and no additional text.\n"
            "2. Use the following keys (camelCase) and include all of them:\n"
            "   - text (string): spoken response in Japanese.\n"
            "   - speakerUuid (string): choose from the list below.\n"
            "   - styleId (integer): choose a styleId belonging to the selected speaker.\n"
            "   - speedScale (float, recommended 0.5-2.0).\n"
            "   - volumeScale (float, recommended 0.5-2.0).\n"
            "   - pitchScale (float, recommended -0.15-0.15).\n"
            "   - intonationScale (float, recommended 0.5-2.0).\n"
            "   - prePhonemeLength (float, seconds before speech, recommended 0.0-1.0).\n"
            "   - postPhonemeLength (float, seconds after speech, recommended 0.0-1.0).\n"
            "   - outputSamplingRate (int, choose 16000/24000/44100/48000).\n"
            "   - prosodyDetail (array): set [] unless detailed mora timing is explicitly required.\n"
            "3. Be concise and align tone with the user's instruction.\n"
            "4. Omit any commentary or explanations outside the JSON.\n"
            "Available COEIROINK speakers and styles:\n"
            f"{speaker_block}"
        )

    def _extract_voice_plan(self, response: Any) -> Optional[Dict[str, Any]]:
        """OllamaからのJSONレスポンスを検証し、音声合成に必要な形式へ変換"""
        if not isinstance(response, dict):
            self.logger.error("レスポンスが辞書形式ではありません")
            return None

        required_keys = [
            "text",
            "speakerUuid",
            "styleId",
            "speedScale",
            "volumeScale",
            "pitchScale",
            "intonationScale",
            "prePhonemeLength",
            "postPhonemeLength",
            "outputSamplingRate",
            "prosodyDetail",
        ]

        missing = [key for key in required_keys if key not in response]
        if missing:
            self.logger.error(f"レスポンスに必要なキーが不足: {missing}")
            return None

        try:
            voice_plan = {
                "text": str(response["text"]),
                "speakerUuid": str(response["speakerUuid"]),
                "styleId": int(response["styleId"]),
                "speedScale": float(response["speedScale"]),
                "volumeScale": float(response["volumeScale"]),
                "pitchScale": float(response["pitchScale"]),
                "intonationScale": float(response["intonationScale"]),
                "prePhonemeLength": float(response["prePhonemeLength"]),
                "postPhonemeLength": float(response["postPhonemeLength"]),
                "outputSamplingRate": int(response["outputSamplingRate"]),
                "prosodyDetail": response.get("prosodyDetail") or [],
            }
        except (TypeError, ValueError) as err:
            self.logger.error(f"レスポンスの型変換に失敗: {err}")
            return None

        return voice_plan

    def _synthesize_and_optionally_play(
        self, voice_plan: Dict[str, Any], play_audio: bool = True
    ) -> Optional[Path]:
        """COEIROINKで音声を合成し、必要に応じて再生"""
        if not self.coeiro_client:
            self.logger.error("COEIROINKクライアントが初期化されていません")
            return None

        speaker = self._find_speaker_by_uuid(voice_plan["speakerUuid"])
        if not speaker:
            self.logger.error(
                f"スピーカーUUIDが一致しません: {voice_plan['speakerUuid']}"
            )
            return None

        style_name = self._resolve_style_name(speaker, voice_plan["styleId"])
        if style_name is None:
            self.logger.error(
                f"スタイルID {voice_plan['styleId']} はスピーカー {speaker.speaker_name} に存在しません"
            )
            return None

        parameters = VoiceParameters(
            speed_scale=voice_plan["speedScale"],
            volume_scale=voice_plan["volumeScale"],
            pitch_scale=voice_plan["pitchScale"],
            intonation_scale=voice_plan["intonationScale"],
            pre_phoneme_length=voice_plan["prePhonemeLength"],
            post_phoneme_length=voice_plan["postPhonemeLength"],
            output_sampling_rate=voice_plan["outputSamplingRate"],
        )
        parameters.validate()

        audio_path = self._prepare_output_path()

        audio_bytes = self.coeiro_client.synthesize(
            text=voice_plan["text"],
            speaker_name=speaker.speaker_name,
            style_name=style_name,
            parameters=parameters,
            use_prosody=bool(voice_plan["prosodyDetail"]),
            prosody_detail=voice_plan.get("prosodyDetail"),
            output_path=audio_path,
        )

        if not audio_bytes:
            self.logger.error("音声データが生成されませんでした")
            return None

        if play_audio and self.audio_player:
            try:
                self.audio_player.play_wav(str(audio_path))
            except Exception as exc:  # pragma: no cover - 実行環境依存
                self.logger.error(f"音声再生に失敗: {exc}")
        elif play_audio and not self.audio_player:
            self.logger.warning("AudioPlayerが利用できないため再生をスキップします")

        self.last_audio_path = audio_path
        return audio_path

    def _prepare_output_path(self) -> Path:
        """音声ファイルの保存先パスを生成"""
        timestamp = int(time.time() * 1000)
        filename = f"response_{timestamp}.wav"
        return self.audio_output_dir / filename

    def _find_speaker_by_uuid(self, speaker_uuid: str) -> Optional[Speaker]:
        """UUIDからスピーカー情報を取得"""
        if not self.coeiro_client:
            return None
        for speaker in self.coeiro_client.speakers.values():
            if speaker.speaker_uuid == speaker_uuid:
                return speaker
        return None

    @staticmethod
    def _resolve_style_name(speaker: Speaker, style_id: int) -> Optional[str]:
        """スタイルIDからスタイル名を取得"""
        for style in speaker.styles:
            if style.get("styleId") == style_id:
                return style.get("styleName")
        return None
