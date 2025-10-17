#!/usr/bin/env python3
"""coeiroink_clientモジュールのテスト"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path
import tempfile
import os

from src.coeiroink_client import (
    Speaker,
    VoiceParameters,
    ProsodyMora,
    SynthesisRequest,
    COEIROINKClient
)


class TestSpeaker:
    """Speakerクラスのテスト"""

    def test_init(self) -> None:
        """初期化テスト"""
        speaker = Speaker(
            speaker_name="つくよみちゃん",
            speaker_uuid="test-uuid-1234",
            styles=[
                {"styleName": "れいせい", "styleId": 0},
                {"styleName": "げんき", "styleId": 1}
            ],
            version="1.0.0"
        )

        assert speaker.speaker_name == "つくよみちゃん"
        assert speaker.speaker_uuid == "test-uuid-1234"
        assert len(speaker.styles) == 2
        assert speaker.version == "1.0.0"

    def test_get_style_id(self) -> None:
        """スタイルID取得のテスト"""
        speaker = Speaker(
            speaker_name="Test Speaker",
            speaker_uuid="uuid-123",
            styles=[
                {"styleName": "style1", "styleId": 100},
                {"styleName": "style2", "styleId": 200}
            ],
            version="1.0.0"
        )

        assert speaker.get_style_id("style1") == 100
        assert speaker.get_style_id("style2") == 200
        assert speaker.get_style_id("nonexistent") is None

    def test_list_styles(self) -> None:
        """スタイルリスト取得のテスト"""
        speaker = Speaker(
            speaker_name="Test Speaker",
            speaker_uuid="uuid-123",
            styles=[
                {"styleName": "style1", "styleId": 100},
                {"styleName": "style2", "styleId": 200}
            ],
            version="1.0.0"
        )

        styles = speaker.list_styles()
        assert styles == ["style1", "style2"]


class TestVoiceParameters:
    """VoiceParametersクラスのテスト"""

    def test_default_values(self) -> None:
        """デフォルト値のテスト"""
        params = VoiceParameters()

        assert params.speed_scale == 1.0
        assert params.volume_scale == 1.0
        assert params.pitch_scale == 0.0
        assert params.intonation_scale == 1.0
        assert params.pre_phoneme_length == 0.1
        assert params.post_phoneme_length == 0.5
        assert params.output_sampling_rate == 24000

    def test_validate_valid_parameters(self) -> None:
        """正常なパラメータの検証テスト"""
        params = VoiceParameters(
            speed_scale=1.0,
            volume_scale=1.0,
            pitch_scale=0.0,
            intonation_scale=1.0,
            pre_phoneme_length=0.1,
            post_phoneme_length=0.5,
            output_sampling_rate=24000
        )

        assert params.validate() is True

    def test_validate_invalid_speed(self) -> None:
        """無効な速度パラメータの検証テスト"""
        params = VoiceParameters(speed_scale=3.0)  # 範囲外
        assert params.validate() is False

    def test_validate_invalid_pitch(self) -> None:
        """無効なピッチパラメータの検証テスト"""
        params = VoiceParameters(pitch_scale=0.5)  # 範囲外
        assert params.validate() is False

    def test_validate_invalid_sampling_rate(self) -> None:
        """無効なサンプリングレートの検証テスト"""
        params = VoiceParameters(output_sampling_rate=32000)  # 未対応
        assert params.validate() is False


class TestProsodyMora:
    """ProsodyMoraクラスのテスト"""

    def test_init(self) -> None:
        """初期化テスト"""
        mora = ProsodyMora(
            phoneme="ko",
            hira="こ",
            accent=1
        )

        assert mora.phoneme == "ko"
        assert mora.hira == "こ"
        assert mora.accent == 1


class TestSynthesisRequest:
    """SynthesisRequestクラスのテスト"""

    def test_to_api_format(self) -> None:
        """API形式変換のテスト"""
        params = VoiceParameters(
            speed_scale=1.2,
            volume_scale=1.1,
            pitch_scale=0.05,
            intonation_scale=1.3
        )

        request = SynthesisRequest(
            speaker_uuid="test-uuid",
            style_id=0,
            text="こんにちは",
            parameters=params,
            prosody_detail=[]
        )

        api_format = request.to_api_format()

        assert api_format["speakerUuid"] == "test-uuid"
        assert api_format["styleId"] == 0
        assert api_format["text"] == "こんにちは"
        assert api_format["speedScale"] == 1.2
        assert api_format["volumeScale"] == 1.1
        assert api_format["pitchScale"] == 0.05
        assert api_format["intonationScale"] == 1.3


class TestCOEIROINKClient:
    """COEIROINKClientクラスのテスト"""

    @patch('src.coeiroink_client.requests.get')
    def test_init_and_load_speakers(self, mock_get: Mock) -> None:
        """初期化とスピーカー読み込みのテスト"""
        # モックレスポンス
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "speakerName": "つくよみちゃん",
                "speakerUuid": "uuid-1",
                "styles": [{"styleName": "れいせい", "styleId": 0}],
                "version": "1.0.0"
            },
            {
                "speakerName": "MANA",
                "speakerUuid": "uuid-2",
                "styles": [{"styleName": "ノーマル", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = COEIROINKClient()

        assert len(client.speakers) == 2
        assert "つくよみちゃん" in client.speakers
        assert "MANA" in client.speakers
        mock_get.assert_called_once_with("http://localhost:50032/v1/speakers", timeout=5)

    @patch('src.coeiroink_client.requests.get')
    def test_list_speakers(self, mock_get: Mock) -> None:
        """スピーカーリスト取得のテスト"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "speakerName": "Speaker1",
                "speakerUuid": "uuid-1",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = COEIROINKClient()
        speakers = client.list_speakers()

        assert speakers == ["Speaker1"]

    @patch('src.coeiroink_client.requests.get')
    def test_get_speaker(self, mock_get: Mock) -> None:
        """スピーカー取得のテスト"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "speakerName": "TestSpeaker",
                "speakerUuid": "uuid-test",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = COEIROINKClient()
        speaker = client.get_speaker("TestSpeaker")

        assert speaker is not None
        assert speaker.speaker_name == "TestSpeaker"
        assert speaker.speaker_uuid == "uuid-test"

        # 存在しないスピーカー
        assert client.get_speaker("NonExistent") is None

    @patch('src.coeiroink_client.requests.post')
    @patch('src.coeiroink_client.requests.get')
    def test_estimate_prosody(self, mock_get: Mock, mock_post: Mock) -> None:
        """韻律推定のテスト"""
        # スピーカー読み込みのモック
        mock_get_response = Mock()
        mock_get_response.json.return_value = []
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response

        # 韻律推定のモック
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            "detail": [[{"phoneme": "ko", "hira": "こ", "accent": 1}]]
        }
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response

        client = COEIROINKClient()
        prosody = client.estimate_prosody("こんにちは")

        assert len(prosody) == 1
        assert prosody[0][0]["phoneme"] == "ko"
        mock_post.assert_called_once()

    @patch('src.coeiroink_client.requests.post')
    @patch('src.coeiroink_client.requests.get')
    def test_synthesize(self, mock_get: Mock, mock_post: Mock) -> None:
        """音声合成のテスト"""
        # スピーカー読み込みのモック
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {
                "speakerName": "TestSpeaker",
                "speakerUuid": "uuid-123",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response

        # 音声合成のモック
        mock_post_response = Mock()
        mock_post_response.content = b'RIFF....WAV'  # ダミーWAVデータ
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response

        client = COEIROINKClient()
        audio = client.synthesize(
            text="テスト",
            speaker_name="TestSpeaker",
            style_name="style1"
        )

        assert audio == b'RIFF....WAV'
        mock_post.assert_called_once()

    @patch('src.coeiroink_client.requests.post')
    @patch('src.coeiroink_client.requests.get')
    def test_synthesize_with_output_path(self, mock_get: Mock, mock_post: Mock) -> None:
        """ファイル保存付き音声合成のテスト"""
        # スピーカー読み込みのモック
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {
                "speakerName": "TestSpeaker",
                "speakerUuid": "uuid-123",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response

        # 音声合成のモック
        mock_post_response = Mock()
        mock_post_response.content = b'WAVDATA'
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response

        # 一時ファイルを使用
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            tmp_path = tmp.name

        try:
            client = COEIROINKClient()
            audio = client.synthesize(
                text="テスト",
                speaker_name="TestSpeaker",
                output_path=Path(tmp_path)
            )

            # ファイルが作成されたことを確認
            assert os.path.exists(tmp_path)
            with open(tmp_path, 'rb') as f:
                assert f.read() == b'WAVDATA'
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @patch('src.coeiroink_client.requests.get')
    def test_synthesize_speaker_not_found(self, mock_get: Mock) -> None:
        """存在しないスピーカーでの合成エラーテスト"""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = COEIROINKClient()

        with pytest.raises(ValueError, match="スピーカー .* が見つかりません"):
            client.synthesize(
                text="テスト",
                speaker_name="NonExistentSpeaker"
            )

    @patch('src.coeiroink_client.requests.post')
    @patch('src.coeiroink_client.requests.get')
    def test_synthesize_with_emotions(self, mock_get: Mock, mock_post: Mock) -> None:
        """感情付き音声合成のテスト"""
        # スピーカー読み込みのモック
        mock_get_response = Mock()
        mock_get_response.json.return_value = [
            {
                "speakerName": "TestSpeaker",
                "speakerUuid": "uuid-123",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_get_response.raise_for_status = Mock()
        mock_get.return_value = mock_get_response

        # 音声合成のモック
        mock_post_response = Mock()
        mock_post_response.content = b'WAVDATA'
        mock_post_response.raise_for_status = Mock()
        mock_post.return_value = mock_post_response

        client = COEIROINKClient()

        segments = [
            {
                "text": "セグメント1",
                "speaker_name": "TestSpeaker"
            },
            {
                "text": "セグメント2",
                "speaker_name": "TestSpeaker"
            }
        ]

        audio_list = client.synthesize_with_emotions(segments)

        assert len(audio_list) == 2
        assert all(audio == b'WAVDATA' for audio in audio_list)

    @patch('src.coeiroink_client.requests.get')
    def test_export_speaker_info(self, mock_get: Mock) -> None:
        """スピーカー情報エクスポートのテスト"""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "speakerName": "Speaker1",
                "speakerUuid": "uuid-1",
                "styles": [{"styleName": "style1", "styleId": 0}],
                "version": "1.0.0"
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = COEIROINKClient()

        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            tmp_path = tmp.name

        try:
            client.export_speaker_info(Path(tmp_path))

            # JSONファイルの内容を確認
            with open(tmp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert len(data) == 1
            assert data[0]["speakerName"] == "Speaker1"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
