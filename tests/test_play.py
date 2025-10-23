#!/usr/bin/env python3
"""音声再生テスト用スクリプト"""

from src.audio_player import AudioPlayer

def main():
    player = AudioPlayer()

    # デバイス一覧を表示
    print("=== 音声出力デバイス一覧 ===")
    player.print_output_devices()

    # デフォルトデバイスで再生
    print("\n【テスト1】デフォルトデバイスで440Hz音声を再生")
    try:
        player.play_wav("samples/test_440hz.wav")
        print("✓ 再生完了\n")
    except Exception as e:
        print(f"✗ エラー: {e}\n")

    # 2つ目のファイルも再生
    print("【テスト2】デフォルトデバイスで880Hz音声を再生")
    try:
        player.play_wav("samples/test_880hz.wav")
        print("✓ 再生完了\n")
    except Exception as e:
        print(f"✗ エラー: {e}\n")

if __name__ == "__main__":
    main()
