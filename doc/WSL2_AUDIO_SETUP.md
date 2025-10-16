# WSL2音声出力設定ガイド

## 概要

このドキュメントでは、WSL2（Windows Subsystem for Linux 2）環境でPython（PyAudio）を使用して音声を再生するための設定手順を説明します。

## 前提条件

- Windows 11またはWindows 10（ビルド21364以降）
- WSL2がインストール済み
- WSLg（WSL GUI）が有効（Windows 11では標準で有効）

## 現状確認

### WSLgが利用可能か確認

```bash
ls -la /mnt/wslg/PulseServer
```

このファイルが存在すれば、WSLgは利用可能です。

### PULSE_SERVER環境変数の確認

```bash
echo $PULSE_SERVER
```

出力例：`unix:/mnt/wslg/PulseServer`

この値が設定されていれば、基本的な環境は整っています。

## セットアップ手順

### 手順1: PulseAudioクライアントツールのインストール

```bash
sudo apt update
sudo apt install -y pulseaudio-utils
```

### 手順2: libasound2-pluginsのインストール

PyAudioがALSA経由でPulseAudioを使用するために必要です。

```bash
sudo apt install -y libasound2-plugins
```

### 手順3: ALSA設定ファイルの作成

ホームディレクトリに`.asoundrc`ファイルを作成し、ALSAがPulseAudioを使用するように設定します。

```bash
cat > ~/.asoundrc << 'EOF'
# PulseAudioをデフォルトのALSAデバイスとして使用
pcm.!default {
    type pulse
    fallback "sysdefault"
    hint {
        show on
        description "Default ALSA Output (via PulseAudio)"
    }
}

ctl.!default {
    type pulse
    fallback "sysdefault"
}

# PulseAudioのPCM定義
pcm.pulse {
    type pulse
}

ctl.pulse {
    type pulse
}
EOF
```

### 手順4: 設定の確認

PulseAudioの接続状態を確認します。

```bash
pactl info
```

以下のような出力が表示されれば成功です：

```
Server String: unix:/mnt/wslg/PulseServer
Server Name: PulseAudio (on Microsoft GmbH Weston Desktop)
...
```

### 手順5: 音声デバイスの確認

```bash
pactl list sinks short
```

出力デバイス（Sink）が表示されれば、音声出力の準備ができています。

## Pythonでの音声再生テスト

プロジェクトのルートディレクトリで以下を実行：

```bash
# 現在のディレクトリを確認
pwd

# テスト用音声ファイルで再生
uv run python test_play.py
```

または、対話的にデバイスを選択して再生：

```bash
uv run python src/audio_player.py samples/test_440hz.wav
```

## トラブルシューティング

### エラー: "Invalid output device (no default output device)"

**原因**: ALSAとPulseAudioの連携が正しく設定されていない

**解決方法**:
1. `.asoundrc`ファイルが正しく作成されているか確認
2. `libasound2-plugins`がインストールされているか確認
3. WSLを再起動してみる: `wsl --shutdown` (PowerShellから実行)

### エラー: "Connection refused"

**原因**: PulseAudioサーバーに接続できない

**解決方法**:
1. WSLgが正しくインストールされているか確認
2. Windowsを再起動してみる
3. `/mnt/wslg/PulseServer`が存在するか確認

### エラー: "pactl: command not found"

**原因**: PulseAudioクライアントツールがインストールされていない

**解決方法**:
```bash
sudo apt install -y pulseaudio-utils
```

### 音が出ない

**確認事項**:
1. Windows側の音量設定が適切か確認
2. Windows側でミュートになっていないか確認
3. Windowsの「設定」→「プライバシーとセキュリティ」→「マイク」でターミナルアプリの権限を確認（入力の場合）

## 環境変数の永続化（オプション）

通常、WSLgが有効な環境では`PULSE_SERVER`は自動設定されますが、もし設定されていない場合は以下を`.bashrc`または`.zshrc`に追加：

```bash
export PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

適用：

```bash
source ~/.bashrc  # または source ~/.zshrc
```

## 参考情報

- **WSLg公式リポジトリ**: https://github.com/microsoft/wslg
- **WSL音声サポートIssue**: https://github.com/microsoft/WSL/issues/5816
- **対応Windowsバージョン**: Windows 11、またはWindows 10（ビルド21364以降）

## まとめ

この設定により、WSL2環境でPython PyAudioを使用した音声再生が可能になります。主なポイント：

1. ✅ WSLgが標準で提供するPulseAudioサーバーを利用
2. ✅ ALSAをPulseAudioのフロントエンドとして設定
3. ✅ 追加のWindows側ソフトウェアは不要
4. ✅ 2025年時点での推奨方法

---

**作成日**: 2025-10-16
**対象プロジェクト**: ai_secretary
**関連ファイル**: [src/audio_player.py](../src/audio_player.py), [test_play.py](../test_play.py)
