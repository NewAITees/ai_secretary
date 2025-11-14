"""Voice-related mixins for :mod:`ai_secretary`."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...coeiroink_client import Speaker, VoiceParameters  # type: ignore


class VoiceMixin:
    """Voice synthesis utilities shared by :class:`AISecretary`."""

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
