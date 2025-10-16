#!/usr/bin/env python3
"""
WAVファイル再生モジュール

設計ドキュメント: doc/audio_player.md (TODO)
関連クラス: なし
"""

import wave
from typing import List, Dict, Optional
import pyaudio


class AudioPlayer:
    """WAVファイルを再生するクラス"""

    def __init__(self) -> None:
        """PyAudioインスタンスを初期化"""
        self.pyaudio = pyaudio.PyAudio()

    def __del__(self) -> None:
        """PyAudioインスタンスを終了"""
        if hasattr(self, 'pyaudio'):
            self.pyaudio.terminate()

    def get_output_devices(self) -> List[Dict[str, any]]:
        """
        利用可能な出力デバイス一覧を取得

        Returns:
            デバイス情報のリスト（各デバイスはdict形式）
        """
        devices = []
        device_count = self.pyaudio.get_device_count()

        for i in range(device_count):
            device_info = self.pyaudio.get_device_info_by_index(i)
            # 出力チャンネルが存在するデバイスのみ
            if device_info['maxOutputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'max_output_channels': device_info['maxOutputChannels'],
                    'default_sample_rate': device_info['defaultSampleRate']
                })

        return devices

    def print_output_devices(self) -> None:
        """利用可能な出力デバイスを表示"""
        devices = self.get_output_devices()
        print("=== 利用可能な音声出力デバイス ===")
        for device in devices:
            print(f"[{device['index']}] {device['name']}")
            print(f"    最大出力チャンネル数: {device['max_output_channels']}")
            print(f"    デフォルトサンプリングレート: {device['default_sample_rate']}Hz")
        print()

    def play_wav(self, wav_path: str, device_index: Optional[int] = None) -> None:
        """
        WAVファイルを再生

        Args:
            wav_path: WAVファイルのパス
            device_index: 出力デバイスのインデックス（Noneの場合はデフォルト）

        Raises:
            FileNotFoundError: WAVファイルが見つからない場合
            wave.Error: WAVファイルの読み込みエラー
        """
        # WAVファイルを開く
        with wave.open(wav_path, 'rb') as wf:
            # ストリームを開く
            stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                output_device_index=device_index
            )

            # チャンクサイズ
            chunk_size = 1024

            # データを読み込んで再生
            data = wf.readframes(chunk_size)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(chunk_size)

            # ストリームを停止・クローズ
            stream.stop_stream()
            stream.close()

    def select_and_play(self, wav_path: str) -> None:
        """
        デバイスを選択してWAVファイルを再生

        Args:
            wav_path: WAVファイルのパス
        """
        self.print_output_devices()

        # デバイスを選択
        device_index = None
        devices = self.get_output_devices()

        if len(devices) > 0:
            while True:
                try:
                    user_input = input("デバイス番号を選択してください（Enterでデフォルト）: ").strip()
                    if user_input == "":
                        print("デフォルトデバイスで再生します")
                        break

                    selected = int(user_input)
                    if any(d['index'] == selected for d in devices):
                        device_index = selected
                        print(f"デバイス[{device_index}]で再生します")
                        break
                    else:
                        print("無効なデバイス番号です。もう一度入力してください。")
                except ValueError:
                    print("数値を入力してください。")

        # 再生
        print(f"再生中: {wav_path}")
        self.play_wav(wav_path, device_index)
        print("再生完了")


def main() -> None:
    """メイン関数（CLIエントリーポイント）"""
    import sys

    if len(sys.argv) < 2:
        print("使用方法: python audio_player.py <WAVファイルパス>")
        sys.exit(1)

    wav_path = sys.argv[1]
    player = AudioPlayer()
    player.select_and_play(wav_path)


if __name__ == "__main__":
    main()
