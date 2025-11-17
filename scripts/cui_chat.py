#!/usr/bin/env python3
"""
CUI版AI秘書チャットインターフェース

Claude Codeが直接テストできるように、標準入出力ベースのシンプルなCLIを提供します。

使用例:
    # 音声なしモード（テスト用）
    uv run python scripts/cui_chat.py --no-audio

    # 音声ありモード
    uv run python scripts/cui_chat.py

    # カスタムモデル指定
    uv run python scripts/cui_chat.py --model llama3.1:8b --no-audio

    # カスタムシステムプロンプト
    uv run python scripts/cui_chat.py --system-prompt "あなたは親切なアシスタントです。" --no-audio
"""

import argparse
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ai_secretary.config import Config
from src.ai_secretary.logger import setup_logger
from src.ai_secretary.secretary import AISecretary


def parse_args():
    """コマンドライン引数をパース"""
    parser = argparse.ArgumentParser(
        description="CUI版AI秘書チャットインターフェース",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s --no-audio
  %(prog)s --model llama3.1:8b
  %(prog)s --system-prompt "あなたは親切なアシスタントです。"
        """,
    )

    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="音声合成・再生を無効化（テスト用）",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="使用するOllamaモデル名（例: llama3.1:8b）",
    )

    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="カスタムシステムプロンプト",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル（デフォルト: INFO）",
    )

    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="既存のセッションIDを指定して会話を再開",
    )

    parser.add_argument(
        "--auto-approve-bash",
        action="store_true",
        help="BASHコマンドを自動承認（テスト用、注意して使用）",
    )

    return parser.parse_args()


def print_banner():
    """起動バナーを表示"""
    print("=" * 60)
    print("AI秘書（CUI版）")
    print("=" * 60)
    print("終了するには 'exit', 'quit', または Ctrl+D を入力してください。")
    print("会話履歴をリセットするには 'reset' を入力してください。")
    print("=" * 60)
    print()


def cui_bash_approval_callback(command: str, reason: str) -> bool:
    """
    CUI版BASH承認コールバック

    標準入力でユーザーに承認を求める

    Args:
        command: 実行するコマンド
        reason: 実行理由

    Returns:
        承認された場合True、拒否された場合False
    """
    print("\n" + "=" * 60)
    print("🔧 BASH コマンド実行の承認が必要です")
    print("=" * 60)
    print(f"理由: {reason}")
    print(f"コマンド: {command}")
    print("=" * 60)

    while True:
        try:
            response = input("実行を承認しますか？ (y/n): ").strip().lower()
            if response in ["y", "yes"]:
                print("✓ 承認されました。コマンドを実行します...\n")
                return True
            elif response in ["n", "no"]:
                print("✗ 拒否されました。コマンドをスキップします。\n")
                return False
            else:
                print("'y' または 'n' を入力してください。")
        except (EOFError, KeyboardInterrupt):
            print("\n✗ 入力が中断されました。コマンドをスキップします。\n")
            return False


def main():
    """メイン処理"""
    args = parse_args()

    # ロガー設定
    setup_logger(log_level=args.log_level)
    logger = logging.getLogger(__name__)

    try:
        # 設定読み込み
        config = Config.from_yaml()

        # コマンドライン引数で上書き
        if args.model:
            config.ollama.model = args.model
        if args.system_prompt:
            config.system_prompt = args.system_prompt

        # AI秘書を初期化（音声無効化オプション対応）
        if args.no_audio:
            logger.info("音声合成・再生を無効化しています")
            secretary = AISecretary(
                config=config,
                coeiroink_client=None,  # 音声合成無効
                audio_player=None,      # 音声再生無効
            )
        else:
            secretary = AISecretary(config=config)

        # CUI版のBASH承認コールバックを設定
        if secretary.bash_executor and secretary.bash_executor.validator:
            if args.auto_approve_bash:
                # 自動承認モード（テスト用）
                secretary.bash_executor.validator.approval_callback = lambda cmd, reason: True
                logger.warning("⚠️  BASH自動承認モードが有効です（テスト用）")
                print("⚠️  BASH自動承認モードが有効です（すべてのコマンドが自動実行されます）\n")
            else:
                # 対話的承認モード
                secretary.bash_executor.validator.approval_callback = cui_bash_approval_callback
                logger.info("CUI版BASH承認コールバックを設定しました")

        # セッション読み込み
        if args.session_id:
            if secretary.load_session(args.session_id):
                print(f"セッション '{args.session_id}' を読み込みました。")
            else:
                print(f"セッション '{args.session_id}' の読み込みに失敗しました。新規セッションを開始します。")

        # バナー表示
        print_banner()

        # 対話ループ
        while True:
            try:
                # ユーザー入力を取得
                user_input = input("You: ").strip()

                # 終了コマンド
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("AI秘書を終了します。")
                    break

                # リセットコマンド
                if user_input.lower() == "reset":
                    secretary.reset_conversation()
                    print("会話履歴をリセットしました。\n")
                    continue

                # 空入力はスキップ
                if not user_input:
                    continue

                # AI秘書に問い合わせ
                response = secretary.chat(
                    user_message=user_input,
                    return_json=False,
                    play_audio=(not args.no_audio),
                )

                # 応答を表示
                print(f"AI: {response}\n")

            except EOFError:
                # Ctrl+D での終了
                print("\nAI秘書を終了します。")
                break
            except KeyboardInterrupt:
                # Ctrl+C での終了
                print("\n\nAI秘書を終了します。")
                break
            except Exception as e:
                logger.error(f"エラーが発生しました: {e}", exc_info=True)
                print(f"エラー: {e}\n")

    except Exception as e:
        logger.error(f"初期化エラー: {e}", exc_info=True)
        print(f"エラー: AI秘書の初期化に失敗しました - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
