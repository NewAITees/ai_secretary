#!/usr/bin/env python3
"""テスト用WAVファイル生成スクリプト"""

import wave
import math
import struct

def generate_test_wav(filename: str, duration: float = 2.0, frequency: int = 440) -> None:
    """
    テスト用のWAVファイルを生成

    Args:
        filename: 出力ファイル名
        duration: 音声の長さ（秒）
        frequency: 周波数（Hz）デフォルトは440Hz（ラ音）
    """
    sample_rate = 44100  # サンプリングレート
    num_channels = 1  # モノラル
    sample_width = 2  # 16bit

    num_frames = int(sample_rate * duration)

    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)

        # 正弦波を生成
        for i in range(num_frames):
            value = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            data = struct.pack('<h', value)
            wav_file.writeframes(data)

    print(f"Generated: {filename} ({duration}s, {frequency}Hz)")

if __name__ == "__main__":
    # テスト用WAVファイルを生成
    generate_test_wav("samples/test_440hz.wav", duration=2.0, frequency=440)
    generate_test_wav("samples/test_880hz.wav", duration=1.0, frequency=880)
    print("サンプルWAVファイルの生成が完了しました")
