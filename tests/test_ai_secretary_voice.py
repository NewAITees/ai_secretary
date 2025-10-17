"""AISecretaryのCOEIROINK連携に関するテスト"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.ai_secretary.config import Config
from src.ai_secretary.secretary import AISecretary
from src.coeiroink_client import Speaker, VoiceParameters


class FakeOllamaClient:
    """固定のJSONレスポンスを返すテスト用Ollamaクライアント"""

    def __init__(self, response: Dict[str, Any]):
        self.response = response
        self.messages: List[Dict[str, str]] = []

    def chat(self, messages, stream=False, return_json=True):  # noqa: D401
        self.messages.extend(messages)
        return self.response


class FakeCoeiroClient:
    """AISecretaryが利用するインターフェースを最小限で再現"""

    def __init__(self, speaker: Speaker):
        self.speakers = {speaker.speaker_name: speaker}
        self.calls: List[Dict[str, Any]] = []

    def synthesize(
        self,
        text: str,
        speaker_name: str,
        style_name: str = None,
        parameters: VoiceParameters = None,
        use_prosody: bool = False,
        prosody_detail=None,
        output_path: Path = None,
    ):
        self.calls.append(
            {
                "text": text,
                "speaker_name": speaker_name,
                "style_name": style_name,
                "parameters": parameters,
                "use_prosody": use_prosody,
                "prosody_detail": prosody_detail,
                "output_path": output_path,
            }
        )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # シンプルなWAVヘッダ(44byte) + 無音データ
            silent_wav = (
                b"RIFF$\x00\x00\x00WAVEfmt "
                b"\x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00"
                b"\x02\x00\x10\x00data\x00\x00\x00\x00"
            )
            output_path.write_bytes(silent_wav)

        return b"fake-audio-bytes"


class FakeAudioPlayer:
    """音声再生を記録するだけのスタブ"""

    def __init__(self):
        self.played: List[str] = []

    def play_wav(self, wav_path: str) -> None:
        self.played.append(wav_path)


@pytest.fixture()
def voice_plan():
    return {
        "text": "テストメッセージです。",
        "speakerUuid": "test-uuid",
        "styleId": 1,
        "speedScale": 1.0,
        "volumeScale": 1.0,
        "pitchScale": 0.0,
        "intonationScale": 1.0,
        "prePhonemeLength": 0.1,
        "postPhonemeLength": 0.5,
        "outputSamplingRate": 24000,
        "prosodyDetail": [],
    }


def test_chat_generates_voice_and_audio(tmp_path, voice_plan):
    speaker = Speaker(
        speaker_name="テストスピーカー",
        speaker_uuid="test-uuid",
        styles=[{"styleName": "ノーマル", "styleId": 1}],
        version="1.0",
    )

    config = Config(
        audio_output_dir=str(tmp_path / "audio"),
        system_prompt=None,
    )

    fake_ollama = FakeOllamaClient(response=voice_plan)
    fake_coeiro = FakeCoeiroClient(speaker=speaker)
    fake_player = FakeAudioPlayer()

    secretary = AISecretary(
        config=config,
        ollama_client=fake_ollama,
        coeiroink_client=fake_coeiro,
        audio_player=fake_player,
    )

    result = secretary.chat("こんにちは", return_json=True)

    assert result["voice_plan"] == voice_plan
    assert result["audio_path"] is not None

    audio_path = Path(result["audio_path"])
    assert audio_path.exists()
    assert fake_player.played == [str(audio_path)]

    assert len(fake_coeiro.calls) == 1
    call = fake_coeiro.calls[0]
    assert call["text"] == voice_plan["text"]
    assert call["prosody_detail"] == voice_plan["prosodyDetail"]
    assert call["parameters"].output_sampling_rate == voice_plan["outputSamplingRate"]
    assert result["played_audio"] is True
