#!/bin/bash
# CUI版AI秘書の自動テストスクリプト

set -e

echo "=== CUI版AI秘書 自動テスト ==="
echo ""

# テスト1: ヘルプ表示
echo "テスト1: ヘルプ表示"
uv run python scripts/cui_chat.py --help > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ ヘルプ表示成功"
else
    echo "✗ ヘルプ表示失敗"
    exit 1
fi
echo ""

# テスト2: 基本的な会話（音声なし）
echo "テスト2: 基本的な会話（音声なし）"
output=$(echo -e "こんにちは\nexit" | timeout 60 uv run python scripts/cui_chat.py --no-audio 2>&1 | grep "AI:")
if echo "$output" | grep -q "AI:"; then
    echo "✓ AI応答を取得"
    echo "応答例: $(echo "$output" | head -1)"
else
    echo "✗ AI応答なし"
    exit 1
fi
echo ""

# テスト3: 複数回の会話
echo "テスト3: 複数回の会話"
output=$(echo -e "天気は？\n今日は何曜日？\nexit" | timeout 60 uv run python scripts/cui_chat.py --no-audio 2>&1 | grep "AI:" | wc -l)
if [ "$output" -ge 2 ]; then
    echo "✓ 複数回の会話成功（${output}回の応答）"
else
    echo "✗ 複数回の会話失敗"
    exit 1
fi
echo ""

# テスト4: リセットコマンド
echo "テスト4: リセットコマンド"
output=$(echo -e "こんにちは\nreset\n世界\nexit" | timeout 60 uv run python scripts/cui_chat.py --no-audio 2>&1)
if echo "$output" | grep -q "会話履歴をリセットしました"; then
    echo "✓ リセットコマンド成功"
else
    echo "✗ リセットコマンド失敗"
    exit 1
fi
echo ""

echo "=== すべてのテスト合格 ==="
