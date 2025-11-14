"""HTTP client for the COEIROINK API."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .models import Speaker, VoiceParameters, SynthesisRequest

logger = logging.getLogger(__name__)


class COEIROINKClient:
    """
    COEIROINKのAPIクライアント

    音声合成の全機能を提供するメインクラス
    """

    def __init__(self, api_url: str = "http://localhost:50032"):
        """
        Args:
            api_url: COEIROINKのAPIサーバーURL
        """
        self.api_url = api_url
        self.speakers: Dict[str, Speaker] = {}
        self._load_speakers()

    def _load_speakers(self) -> None:
        """利用可能なスピーカー情報をAPIから取得"""
        try:
            response = requests.get(f"{self.api_url}/v1/speakers", timeout=5)
            response.raise_for_status()

            for item in response.json():
                speaker = Speaker(
                    speaker_name=item['speakerName'],
                    speaker_uuid=item['speakerUuid'],
                    styles=item['styles'],
                    version=item['version']
                )
                self.speakers[speaker.speaker_name] = speaker

            logger.info(f"スピーカー {len(self.speakers)} 個を読み込みました")
        except requests.exceptions.RequestException as e:
            logger.error(f"スピーカー情報の取得に失敗: {e}")
            raise

    def list_speakers(self) -> List[str]:
        """利用可能なスピーカー名のリストを返す"""
        return list(self.speakers.keys())

    def get_speaker(self, speaker_name: str) -> Optional[Speaker]:
        """スピーカー名からSpeakerオブジェクトを取得"""
        return self.speakers.get(speaker_name)

    def estimate_prosody(self, text: str) -> List[List[Dict]]:
        """
        テキストから韻律情報を推定

        Args:
            text: 音声合成するテキスト

        Returns:
            韻律詳細情報
        """
        try:
            response = requests.post(
                f"{self.api_url}/v1/estimate_prosody",
                headers={"Content-Type": "application/json"},
                json={"text": text},
                timeout=10
            )
            response.raise_for_status()
            prosody_data = response.json()
            return prosody_data.get('detail', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"韻律推定に失敗: {e}")
            return []

    def synthesize(
        self,
        text: str,
        speaker_name: str,
        style_name: str = None,
        parameters: VoiceParameters = None,
        use_prosody: bool = False,
        prosody_detail: Optional[List[List[Dict]]] = None,
        output_path: Optional[Path] = None
    ) -> bytes:
        """
        音声合成のメイン関数

        Args:
            text: 合成するテキスト
            speaker_name: スピーカー名
            style_name: スタイル名(Noneの場合は最初のスタイル)
            parameters: 音声パラメータ
            use_prosody: 韻律情報を自動推定して使用するか
            prosody_detail: 事前に用意された韻律情報（Noneの場合は未指定）
            output_path: 保存先パス(Noneの場合は保存しない)

        Returns:
            音声データ(wavフォーマット)
        """
        # スピーカー取得
        speaker = self.get_speaker(speaker_name)
        if not speaker:
            raise ValueError(f"スピーカー '{speaker_name}' が見つかりません")

        # スタイルID取得
        if style_name:
            style_id = speaker.get_style_id(style_name)
            if style_id is None:
                raise ValueError(f"スタイル '{style_name}' が見つかりません")
        else:
            style_id = speaker.styles[0]['styleId']

        # パラメータ設定
        if parameters is None:
            parameters = VoiceParameters()

        if not parameters.validate():
            logger.warning("パラメータに問題がありますが、続行します")

        # 韻律情報取得(オプション)
        prosody_payload: List[List[Dict]] = []
        if prosody_detail is not None:
            prosody_payload = prosody_detail
            logger.info("事前計算された韻律情報を使用します")
        elif use_prosody:
            prosody_payload = self.estimate_prosody(text)
            logger.info("韻律情報を自動推定して使用します")

        # リクエスト作成
        request = SynthesisRequest(
            speaker_uuid=speaker.speaker_uuid,
            style_id=style_id,
            text=text,
            parameters=parameters,
            prosody_detail=prosody_payload
        )

        # API呼び出し
        try:
            response = requests.post(
                f"{self.api_url}/v1/synthesis",
                headers={
                    "accept": "audio/wav",
                    "Content-Type": "application/json"
                },
                json=request.to_api_format(),
                timeout=30
            )
            response.raise_for_status()

            audio_data = response.content
            logger.info(f"音声合成成功: {len(audio_data)} bytes")

            # ファイル保存
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"音声ファイル保存: {output_path}")

            return audio_data

        except requests.exceptions.RequestException as e:
            logger.error(f"音声合成に失敗: {e}")
            raise

    def synthesize_with_emotions(
        self,
        text_segments: List[Dict[str, Any]],
        output_path: Optional[Path] = None
    ) -> List[bytes]:
        """
        感情付き音声合成

        テキストセグメントごとに異なるパラメータで合成

        Args:
            text_segments: セグメントリスト
                [
                    {
                        "text": "こんにちは",
                        "speaker_name": "つくよみちゃん",
                        "style_name": "れいせい",
                        "parameters": VoiceParameters(...)
                    },
                    ...
                ]
            output_path: 結合音声の保存先(Noneの場合は結合しない)

        Returns:
            各セグメントの音声データリスト
        """
        audio_segments = []

        for i, segment in enumerate(text_segments):
            logger.info(f"セグメント {i+1}/{len(text_segments)} を合成中...")

            audio = self.synthesize(
                text=segment['text'],
                speaker_name=segment['speaker_name'],
                style_name=segment.get('style_name'),
                parameters=segment.get('parameters'),
                use_prosody=segment.get('use_prosody', False)
            )
            audio_segments.append(audio)

        # 音声結合が必要な場合はffmpegなどを使用
        # ここでは個別の音声を返すのみ

        logger.info(f"全 {len(audio_segments)} セグメントの合成完了")
        return audio_segments

    def export_speaker_info(self, output_path: Path) -> None:
        """スピーカー情報をJSONファイルに出力"""
        speaker_data = []
        for speaker in self.speakers.values():
            speaker_data.append({
                "speakerName": speaker.speaker_name,
                "speakerUuid": speaker.speaker_uuid,
                "styles": speaker.styles,
                "version": speaker.version
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(speaker_data, f, ensure_ascii=False, indent=2)

        logger.info(f"スピーカー情報を {output_path} に保存しました")


