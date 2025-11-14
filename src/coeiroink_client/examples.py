"""Executable usage examples for the COEIROINK client."""

from __future__ import annotations

from pathlib import Path

from .client import COEIROINKClient
from .models import VoiceParameters

# ========================================
# 使用例
# ========================================

def example_basic():
    """基本的な使用例"""
    print("\n=== 基本的な使用例 ===")

    # クライアント初期化
    client = COEIROINKClient()

    # 利用可能なスピーカーを表示
    print("利用可能なスピーカー:")
    for name in client.list_speakers():
        speaker = client.get_speaker(name)
        print(f"  - {name}: {speaker.list_styles()}")

    # シンプルな音声合成
    audio = client.synthesize(
        text="こんにちは、今日はいい天気ですね。",
        speaker_name="つくよみちゃん",
        style_name="れいせい",
        output_path="output_basic.wav"
    )
    print(f"音声合成完了: {len(audio)} bytes")


def example_with_parameters():
    """パラメータ調整の例"""
    print("\n=== パラメータ調整の例 ===")

    client = COEIROINKClient()

    # カスタムパラメータで合成
    params = VoiceParameters(
        speed_scale=1.2,      # 少し速く
        volume_scale=1.1,     # 少し大きく
        pitch_scale=0.05,     # 少し高く
        intonation_scale=1.3  # 抑揚を強く
    )

    audio = client.synthesize(
        text="感情豊かに話してみます!",
        speaker_name="つくよみちゃん",
        parameters=params,
        use_prosody=True,  # 韻律情報を使用
        output_path="output_expressive.wav"
    )
    print(f"表現力豊かな音声合成完了: {len(audio)} bytes")


def example_multi_segment():
    """複数セグメント合成の例"""
    print("\n=== 複数セグメント合成の例 ===")

    client = COEIROINKClient()

    # 場面ごとに異なるパラメータで合成
    segments = [
        {
            "text": "おはようございます。",
            "speaker_name": "つくよみちゃん",
            "style_name": "れいせい",
            "parameters": VoiceParameters(speed_scale=1.0)
        },
        {
            "text": "今日は楽しい日になりそうです!",
            "speaker_name": "つくよみちゃん",
            "style_name": "れいせい",
            "parameters": VoiceParameters(
                speed_scale=1.1,
                pitch_scale=0.05,
                intonation_scale=1.4
            )
        }
    ]

    audio_list = client.synthesize_with_emotions(segments)
    print(f"{len(audio_list)} セグメントの音声を生成しました")


def example_export_speakers():
    """スピーカー情報のエクスポート例"""
    print("\n=== スピーカー情報のエクスポート ===")

    client = COEIROINKClient()
    client.export_speaker_info(Path("speakers.json"))
    print("speakers.json に情報を保存しました")


if __name__ == "__main__":
    print("COEIROINK音声合成システム")
    print("注意: COEIROINKを起動してから実行してください")
    print("=" * 50)

    try:
        # 各種使用例を実行
        example_basic()
        example_with_parameters()
        example_multi_segment()
        example_export_speakers()

        print("\n" + "=" * 50)
        print("全ての例の実行が完了しました!")

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        print("COEIROINKが起動していることを確認してください")

