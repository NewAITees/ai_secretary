#!/usr/bin/env python3
"""audio_playerモジュールのテスト"""

import pytest
import wave
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from src.audio_player import AudioPlayer


class TestAudioPlayer:
    """AudioPlayerクラスのテスト"""

    def test_init(self) -> None:
        """初期化テスト"""
        with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
            player = AudioPlayer()
            assert player.pyaudio is not None
            mock_pyaudio.assert_called_once()

    def test_get_output_devices(self) -> None:
        """出力デバイス一覧取得のテスト"""
        with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
            # モックの設定
            mock_instance = mock_pyaudio.return_value
            mock_instance.get_device_count.return_value = 3

            # デバイス情報のモック
            def get_device_info(index: int) -> dict:
                devices = [
                    {
                        'index': 0,
                        'name': 'Device 0 (Input Only)',
                        'maxOutputChannels': 0,
                        'defaultSampleRate': 44100.0
                    },
                    {
                        'index': 1,
                        'name': 'Device 1 (Output)',
                        'maxOutputChannels': 2,
                        'defaultSampleRate': 48000.0
                    },
                    {
                        'index': 2,
                        'name': 'Device 2 (Output)',
                        'maxOutputChannels': 2,
                        'defaultSampleRate': 44100.0
                    }
                ]
                return devices[index]

            mock_instance.get_device_info_by_index.side_effect = get_device_info

            player = AudioPlayer()
            devices = player.get_output_devices()

            # 出力デバイスのみが返されることを確認（Device 0は除外）
            assert len(devices) == 2
            assert devices[0]['index'] == 1
            assert devices[0]['name'] == 'Device 1 (Output)'
            assert devices[1]['index'] == 2

    def test_print_output_devices(self, capsys) -> None:
        """デバイス一覧表示のテスト"""
        with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
            mock_instance = mock_pyaudio.return_value
            mock_instance.get_device_count.return_value = 1
            mock_instance.get_device_info_by_index.return_value = {
                'index': 0,
                'name': 'Test Device',
                'maxOutputChannels': 2,
                'defaultSampleRate': 44100.0
            }

            player = AudioPlayer()
            player.print_output_devices()

            captured = capsys.readouterr()
            assert "利用可能な音声出力デバイス" in captured.out
            assert "Test Device" in captured.out

    def test_play_wav_with_valid_file(self) -> None:
        """正常なWAVファイル再生のテスト"""
        # テンポラリWAVファイルを作成
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            # シンプルなWAVファイルを作成
            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b'\x00\x00' * 1000)  # 無音データ

            with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
                mock_instance = mock_pyaudio.return_value
                mock_stream = MagicMock()
                mock_instance.open.return_value = mock_stream

                player = AudioPlayer()
                player.play_wav(tmp_path, device_index=None)

                # ストリームが開かれたことを確認
                mock_instance.open.assert_called_once()
                # ストリームが適切にクローズされたことを確認
                mock_stream.stop_stream.assert_called_once()
                mock_stream.close.assert_called_once()

        finally:
            # テンポラリファイルを削除
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_play_wav_with_device_index(self) -> None:
        """デバイス指定でのWAV再生テスト"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b'\x00\x00' * 1000)

            with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
                mock_instance = mock_pyaudio.return_value
                mock_stream = MagicMock()
                mock_instance.open.return_value = mock_stream

                player = AudioPlayer()
                player.play_wav(tmp_path, device_index=2)

                # device_indexが渡されたことを確認
                call_kwargs = mock_instance.open.call_args[1]
                assert call_kwargs['output_device_index'] == 2

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_play_wav_file_not_found(self) -> None:
        """存在しないファイルのテスト"""
        with patch('src.audio_player.pyaudio.PyAudio'):
            player = AudioPlayer()
            with pytest.raises(FileNotFoundError):
                player.play_wav('/path/to/nonexistent/file.wav')

    def test_select_and_play_with_default_device(self) -> None:
        """デフォルトデバイスでの再生テスト"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            tmp_path = tmp_file.name

        try:
            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b'\x00\x00' * 1000)

            with patch('src.audio_player.pyaudio.PyAudio') as mock_pyaudio:
                mock_instance = mock_pyaudio.return_value
                mock_instance.get_device_count.return_value = 1
                mock_instance.get_device_info_by_index.return_value = {
                    'index': 0,
                    'name': 'Test Device',
                    'maxOutputChannels': 2,
                    'defaultSampleRate': 44100.0
                }
                mock_stream = MagicMock()
                mock_instance.open.return_value = mock_stream

                with patch('builtins.input', return_value=''):  # Enterキー
                    player = AudioPlayer()
                    player.select_and_play(tmp_path)

                # play_wavが呼ばれたことを確認
                mock_instance.open.assert_called_once()

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
