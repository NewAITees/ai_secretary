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

# テスト3: 複数回の会話（シンプルな質問のみ、BASH実行なし）
echo "テスト3: 複数回の会話"
output=$(echo -e "1+1は？\n2+2は？\nexit" | timeout 60 uv run python scripts/cui_chat.py --no-audio 2>&1 | grep "AI:" | wc -l)
if [ "$output" -ge 2 ]; then
    echo "✓ 複数回の会話成功（${output}回の応答）"
else
    echo "✗ 複数回の会話失敗（応答数: ${output}）"
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

# テスト5: 3段階BASHフロー（自動承認モード、時間がかかるため任意実行）
if [ "${RUN_BASH_TEST:-0}" = "1" ]; then
    echo "テスト5: 3段階BASHフロー（BASH実行含む）"
    output=$(echo -e "今日の日付を教えて\nexit" | timeout 120 uv run python scripts/cui_chat.py --no-audio --auto-approve-bash 2>&1)
    if echo "$output" | grep -q "AI:"; then
        echo "✓ BASH統合テスト成功"
        # BASHログの確認
        if echo "$output" | grep -q "Executing bash command"; then
            echo "  ℹ BASH実行が検出されました"
        fi
        # 自動承認の確認
        if echo "$output" | grep -q "BASH自動承認モードが有効です"; then
            echo "  ℹ 自動承認モードで実行されました"
        fi
    else
        echo "✗ BASH統合テスト失敗"
        exit 1
    fi
    echo ""
fi

echo "=== すべてのテスト合格 ==="
echo ""
echo "ℹ BASH統合テスト（テスト5）を実行するには:"
echo "  RUN_BASH_TEST=1 ./scripts/test_cui_chat.sh"
