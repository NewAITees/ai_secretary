"""
AI秘書のメインモジュール

設計ドキュメント参照: doc/design/secretary.md
関連クラス:
  - config.Config: 設定管理
  - logger.setup_logger: ロギング設定
  - ollama_client.OllamaClient: Ollama API通信
"""

import json
import logging
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .ollama_client import OllamaClient
from ..coeiroink_client import COEIROINKClient, VoiceParameters, Speaker  # type: ignore

try:
    from ..audio_player import AudioPlayer  # type: ignore
except Exception:  # pragma: no cover - AudioPlayerを利用できない環境向け
    AudioPlayer = None  # type: ignore[assignment]

try:
    from ..bash_executor import CommandExecutor  # type: ignore
except Exception:  # pragma: no cover - BashExecutorを利用できない環境向け
    CommandExecutor = None  # type: ignore[assignment]

try:
    from ..chat_history import ChatHistoryRepository  # type: ignore
except Exception:  # pragma: no cover - ChatHistoryを利用できない環境向け
    ChatHistoryRepository = None  # type: ignore[assignment]


class AISecretary:
    """AI秘書のメインクラス"""

    def __init__(
        self,
        config: Optional[Config] = None,
        ollama_client: Optional[OllamaClient] = None,
        coeiroink_client: Optional[COEIROINKClient] = None,
        audio_player: Optional["AudioPlayer"] = None,
        bash_executor: Optional["CommandExecutor"] = None,
        chat_history_repo: Optional["ChatHistoryRepository"] = None,
    ):
        """
        初期化

        Args:
            config: 設定オブジェクト。Noneの場合はYAMLファイルから読み込む
            ollama_client: 依存性注入用のOllamaクライアント
            coeiroink_client: 依存性注入用のCOEIROINKクライアント
            audio_player: 依存性注入用のAudioPlayer
            bash_executor: 依存性注入用のBashExecutor
            chat_history_repo: 依存性注入用のChatHistoryRepository
        """
        self.config = config or Config.from_yaml()
        self.logger = logging.getLogger(__name__)

        # Ollamaクライアントの初期化
        self.ollama_client = ollama_client or OllamaClient(
            host=self.config.ollama.host,
            model=self.config.ollama.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # COEIROINKクライアントとAudioPlayer
        self.coeiro_client: Optional[COEIROINKClient]
        if coeiroink_client is not None:
            self.coeiro_client = coeiroink_client
        else:
            try:
                self.coeiro_client = COEIROINKClient(
                    api_url=self.config.coeiroink_api_url
                )
            except Exception as e:  # pragma: no cover - 実行環境依存
                self.logger.error(f"COEIROINKクライアント初期化失敗: {e}")
                self.coeiro_client = None

        self.audio_player: Optional["AudioPlayer"] = audio_player
        if self.audio_player is None and AudioPlayer is not None:
            try:
                self.audio_player = AudioPlayer()
            except Exception as e:  # pragma: no cover - 実行環境依存
                self.logger.error(f"AudioPlayer初期化失敗: {e}")
                self.audio_player = None

        # 音声出力ディレクトリ
        self.audio_output_dir = Path(self.config.audio_output_dir)
        self.audio_output_dir.mkdir(parents=True, exist_ok=True)
        self.last_audio_path: Optional[Path] = None

        # 会話履歴の初期化
        self.conversation_history: List[Dict[str, str]] = []

        # システムプロンプトの設定
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )

        # COEIROINK利用ガイダンスを追加
        voice_instruction = self._build_voice_instruction()
        if voice_instruction:
            self.conversation_history.append(
                {"role": "system", "content": voice_instruction}
            )

        # BashExecutorの初期化
        self.bash_executor: Optional["CommandExecutor"] = bash_executor
        self.bash_approval_callback: Optional[Any] = None  # 承認コールバック
        if self.bash_executor is None:
            try:
                from ..bash_executor import create_executor, CommandValidator

                self.bash_executor = create_executor()
                # 承認コールバックを設定
                if self.bash_executor and self.bash_executor.validator:
                    self.bash_executor.validator.approval_callback = self._request_bash_approval
                self.logger.info("BashExecutor initialized successfully")
            except Exception as e:
                self.logger.warning(f"BashExecutor初期化失敗（機能は無効化されます）: {e}")
                self.bash_executor = None

        # BASH実行ガイダンスを追加
        bash_instruction = self._build_bash_instruction()
        if bash_instruction and self.bash_executor:
            self.conversation_history.append({"role": "system", "content": bash_instruction})

        # ChatHistoryRepositoryの初期化
        self.chat_history_repo: Optional["ChatHistoryRepository"] = chat_history_repo
        if self.chat_history_repo is None and ChatHistoryRepository is not None:
            try:
                self.chat_history_repo = ChatHistoryRepository()
                self.logger.info("ChatHistoryRepository initialized successfully")
            except Exception as e:
                self.logger.warning(f"ChatHistoryRepository初期化失敗（機能は無効化されます）: {e}")
                self.chat_history_repo = None

        # セッション管理
        self.session_id = str(uuid.uuid4())  # 新規セッションID
        self.session_title: Optional[str] = None  # セッションタイトル（最初のメッセージから生成）

    def chat(
        self,
        user_message: str,
        return_json: bool = False,
        play_audio: bool = True,
        model: Optional[str] = None,
        max_bash_retry: int = 2,
        enable_bash_verification: bool = True,
    ) -> Any:
        """
        ユーザーメッセージに対して応答（3段階BASHフロー対応）

        Args:
            user_message: ユーザーからのメッセージ
            return_json: JSON形式で応答を返すか（デフォルト: False、テキストのみ返す）
            play_audio: 生成した音声を即時再生するか
            model: 使用するモデル名（Noneの場合はデフォルトモデルを使用）
            max_bash_retry: BASH実行の最大再試行回数（デフォルト: 2）
            enable_bash_verification: BASH検証ステップを有効化（デフォルト: True）

        Returns:
            AI秘書からの応答（辞書形式またはテキスト）
        """
        # ユーザーメッセージを履歴に追加
        self.conversation_history.append({"role": "user", "content": user_message})

        # モデルを一時的に切り替える場合
        original_model = self.ollama_client.model
        if model is not None:
            self.ollama_client.model = model

        try:
            # Ollamaから応答を取得（デフォルトでJSON形式）
            raw_response = self.ollama_client.chat(
                messages=self.conversation_history, stream=False, return_json=True
            )

            # 3段階BASHフロー
            final_response = self._execute_bash_workflow(
                user_message=user_message,
                initial_response=raw_response,
                max_retry=max_bash_retry,
                enable_verification=enable_bash_verification
            )

            # アシスタントの応答を履歴に追加（JSON文字列として）
            response_str = json.dumps(final_response, ensure_ascii=False)
            self.conversation_history.append(
                {"role": "assistant", "content": response_str}
            )

            # チャット履歴を自動保存
            self._save_chat_history(user_message)

            voice_plan = None
            audio_path = None
            # COEIROINKクライアントが有効な場合のみ音声合成を試みる
            if self.coeiro_client is not None:
                voice_plan = self._extract_voice_plan(final_response)
                if voice_plan is not None:
                    audio_path = self._synthesize_and_optionally_play(
                        voice_plan, play_audio=play_audio
                    )

            result: Dict[str, Any] = {
                "voice_plan": voice_plan,
                "audio_path": str(audio_path) if audio_path else None,
                "played_audio": bool(audio_path and play_audio and self.audio_player),
            }

            if return_json:
                result["raw_response"] = raw_response
                return result
            if voice_plan:
                return voice_plan.get("text", json.dumps(voice_plan, ensure_ascii=False))
            return json.dumps(raw_response, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Chat error: {e}")
            return {"error": str(e)} if return_json else f"エラーが発生しました: {str(e)}"
        finally:
            # モデルを元に戻す
            if model is not None:
                self.ollama_client.model = original_model

    def reset_conversation(self):
        """会話履歴をリセット（新規セッションとして扱う）"""
        self.conversation_history.clear()
        if self.config.system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": self.config.system_prompt}
            )
        # 新しいセッションIDを生成
        self.session_id = str(uuid.uuid4())
        self.session_title = None
        self.logger.info(f"会話履歴をリセットしました (new session: {self.session_id})")

    def get_available_models(self) -> List[str]:
        """利用可能なモデルのリストを取得"""
        return self.ollama_client.list_models()

    def start(self):
        """秘書システムを起動"""
        self.logger.info("AI秘書システムを起動します")
        self.logger.info(f"使用モデル: {self.config.ollama.model}")
        self.logger.info(f"Ollamaホスト: {self.config.ollama.host}")

    def stop(self):
        """秘書システムを停止"""
        self.logger.info("AI秘書システムを停止します")

    def load_session(self, session_id: str) -> bool:
        """
        過去のチャットセッションを読み込んで会話を再開

        Args:
            session_id: 読み込むセッションのID

        Returns:
            読み込み成功時True、失敗時False
        """
        if not self.chat_history_repo:
            self.logger.warning("ChatHistoryRepository未初期化のためセッション読み込みをスキップ")
            return False

        try:
            session = self.chat_history_repo.get_session(session_id)
            if not session:
                self.logger.warning(f"セッションが見つかりません: {session_id}")
                return False

            # セッション情報を復元
            self.session_id = session.session_id
            self.session_title = session.title
            self.conversation_history = session.messages

            self.logger.info(f"セッションを読み込みました: {session.title} ({session_id})")
            return True

        except Exception as e:
            self.logger.error(f"セッション読み込みに失敗: {e}")
            return False

    # =========================================================
    # 内部ユーティリティ
    # =========================================================

    def _save_chat_history(self, user_message: str) -> None:
        """
        チャット履歴を自動保存

        Args:
            user_message: ユーザーの最新メッセージ（タイトル生成用）
        """
        if not self.chat_history_repo:
            return

        # タイトル未設定なら最初のユーザーメッセージから生成
        if self.session_title is None:
            self.session_title = self._generate_title(user_message)

        try:
            self.chat_history_repo.save_or_update(
                session_id=self.session_id,
                title=self.session_title,
                messages=self.conversation_history
            )
            self.logger.debug(f"チャット履歴を保存しました: {self.session_title}")
        except Exception as e:
            self.logger.error(f"チャット履歴の保存に失敗: {e}")

    @staticmethod
    def _generate_title(user_message: str) -> str:
        """
        ユーザーメッセージからセッションタイトルを生成

        Args:
            user_message: ユーザーメッセージ

        Returns:
            タイトル（最大30文字）
        """
        # 改行や余分な空白を削除
        title = " ".join(user_message.split())
        # 最大30文字に制限
        if len(title) > 30:
            title = title[:30] + "..."
        return title

    def _build_voice_instruction(self) -> str:
        """COEIROINK利用のためのプロンプトを生成"""
        if not self.coeiro_client or not self.coeiro_client.speakers:
            return ""

        speaker_lines = []
        for speaker in sorted(
            self.coeiro_client.speakers.values(), key=lambda s: s.speaker_name
        ):
            style_descriptions = ", ".join(
                f"{style['styleName']} (styleId={style['styleId']})"
                for style in speaker.styles
            )
            speaker_lines.append(
                f"- speakerName: {speaker.speaker_name}, speakerUuid: {speaker.speaker_uuid}, styles: {style_descriptions}"
            )

        speaker_block = "\n".join(speaker_lines)
        return (
            "You are a response planner that prepares JSON payloads for the COEIROINK "
            "voice synthesis API. Follow these rules strictly:\n"
            "1. Answer ONLY with valid JSON and no additional text.\n"
            "2. Use the following keys (camelCase) and include all of them:\n"
            "   - text (string): spoken response in Japanese.\n"
            "   - speakerUuid (string): choose from the list below.\n"
            "   - styleId (integer): choose a styleId belonging to the selected speaker.\n"
            "   - speedScale (float, recommended 0.5-2.0).\n"
            "   - volumeScale (float, recommended 0.5-2.0).\n"
            "   - pitchScale (float, recommended -0.15-0.15).\n"
            "   - intonationScale (float, recommended 0.5-2.0).\n"
            "   - prePhonemeLength (float, seconds before speech, recommended 0.0-1.0).\n"
            "   - postPhonemeLength (float, seconds after speech, recommended 0.0-1.0).\n"
            "   - outputSamplingRate (int, choose 16000/24000/44100/48000).\n"
            "   - prosodyDetail (array): set [] unless detailed mora timing is explicitly required.\n"
            "3. Be concise and align tone with the user's instruction.\n"
            "4. Omit any commentary or explanations outside the JSON.\n"
            "Available COEIROINK speakers and styles:\n"
            f"{speaker_block}"
        )

    def _build_bash_instruction(self) -> str:
        """BASH実行機能のためのプロンプトを生成"""
        if not self.bash_executor:
            return ""

        # ホワイトリストから利用可能なコマンドを取得
        try:
            validator = self.bash_executor.validator
            allowed_commands = sorted(list(validator.allowed_commands))[:50]  # 最大50個表示
            commands_preview = ", ".join(allowed_commands[:30])
            if len(allowed_commands) > 30:
                commands_preview += f"... (他{len(allowed_commands) - 30}個)"
        except Exception:
            commands_preview = "ls, pwd, cat, mkdir, git, uv, など"

        return (
            "## BASHコマンド実行機能\n\n"
            "ファイル操作、情報取得、外部ツール呼び出しが必要な場合、bashActionsフィールドを使用してください。\n\n"
            "### 利用可能なコマンド（抜粋）\n"
            f"{commands_preview}\n\n"
            "### 応答例\n"
            "```json\n"
            "{\n"
            '  "text": "現在のディレクトリを確認します。",\n'
            '  "bashActions": [\n'
            '    {"command": "pwd", "reason": "現在のディレクトリを確認"}\n'
            "  ],\n"
            '  "speakerUuid": "...",\n'
            "  ...\n"
            "}\n"
            "```\n\n"
            "### 制約事項\n"
            "- ホワイトリストに登録されたコマンドのみ実行可能\n"
            "- タイムアウトは30秒です\n"
            f"- ルートディレクトリ外への移動は制限されています（root: {self.bash_executor.root_dir}）\n"
            "- 危険なコマンド（rm -rf、chmod 777など）は実行できません\n"
        )

    # =========================================================
    # BASH 3段階ワークフロー - Step2/Step3専用スキーマ&プロンプト
    # =========================================================
    # 注: Step1はconfig/system_prompt.txtで定義されたシステムプロンプトを使用

    def _get_step2_json_schema(self) -> str:
        """
        Step 2用JSONスキーマ定義（実行結果を踏まえた音声応答）

        COEIROINKクライアントが無効な場合はtextのみでも可

        Returns:
            JSONスキーマ定義文字列
        """
        if self.coeiro_client is None:
            # COEIROINKが無効な場合はtextのみ
            return '''
{
  "text": "BASH実行結果を踏まえたユーザーへの応答文（日本語）"
}
'''

        # COEIROINKが有効な場合は音声フィールドも含める
        return '''
{
  "text": "BASH実行結果を踏まえたユーザーへの応答文（日本語）",
  "speakerUuid": "COEIROINKスピーカーUUID",
  "styleId": 0,
  "speedScale": 1.0,
  "volumeScale": 1.0,
  "pitchScale": 0.0,
  "intonationScale": 1.0,
  "prePhonemeLength": 0.1,
  "postPhonemeLength": 0.1,
  "outputSamplingRate": 24000,
  "prosodyDetail": []
}
'''

    def _get_step3_json_schema(self) -> str:
        """
        Step 3用JSONスキーマ定義（検証結果のみ）

        Returns:
            JSONスキーマ定義文字列
        """
        return '''
{
  "success": true,
  "reason": "検証結果の詳細説明",
  "suggestion": "失敗時の改善提案（成功時は空文字）"
}
'''

    def _build_step2_prompt(self, user_message: str, bash_results: list) -> str:
        """
        Step 2専用プロンプト: 実行結果を踏まえた回答生成

        Args:
            user_message: ユーザーのメッセージ
            bash_results: BASH実行結果

        Returns:
            Step 2用のシステムプロンプト
        """
        result_context = self._format_bash_results(bash_results)
        schema = self._get_step2_json_schema()

        return (
            "## Step 2: BASH実行結果を踏まえた回答生成\n\n"
            f"**ユーザーの質問**: {user_message}\n\n"
            f"**BASH実行結果**:\n```\n{result_context}\n```\n\n"
            "### 指示\n"
            "上記のBASH実行結果を**必ず確認**し、その内容を踏まえてユーザーの質問に適切に回答してください。\n\n"
            "### 応答のポイント\n"
            "- 実行結果の要点をわかりやすく説明する\n"
            "- エラーが発生した場合は、エラー内容を説明し対処法を提案する\n"
            "- 実行成功時は、結果の意味をユーザーにわかりやすく伝える\n"
            "- 実行結果を無視せず、必ず言及する\n\n"
            "### 応答形式\n"
            "以下のJSONスキーマに厳密に従って応答してください:\n"
            f"```json\n{schema}```\n\n"
            "**重要事項**:\n"
            "- `bashActions` フィールドは**含めないでください**（Step 2では不要）\n"
            "- 必ずすべてのCOEIROINKフィールドを含めてください\n"
            "- JSON以外のテキストは一切出力しないでください\n"
        )

    def _build_step3_prompt(
        self, user_message: str, bash_results: list, response: dict
    ) -> str:
        """
        Step 3専用プロンプト: 検証のみに集中

        Args:
            user_message: ユーザーのメッセージ
            bash_results: BASH実行結果
            response: Step 2で生成した回答

        Returns:
            Step 3用のシステムプロンプト
        """
        bash_summary = "\n".join([
            f"- コマンド: `{r['command']}`, "
            f"終了コード: {r['result']['exit_code'] if r['result'] else 'エラー'}, "
            f"エラー: {r.get('error', 'なし')}"
            for r in bash_results
        ])

        schema = self._get_step3_json_schema()

        return (
            "## Step 3: タスク達成度と回答の整合性を検証\n\n"
            f"**ユーザーの質問**: {user_message}\n\n"
            f"**実行したBASHコマンド**:\n{bash_summary}\n\n"
            f"**生成した回答**: {response.get('text', '')}\n\n"
            "### 検証項目\n"
            "以下の3点を厳密に評価してください:\n\n"
            "1. **BASHコマンドは正常に実行されましたか？**\n"
            "   - すべてのコマンドのexit_codeが0か確認\n"
            "   - エラーが発生していないか確認\n\n"
            "2. **回答はBASHコマンドの実行結果を正しく反映していますか？**\n"
            "   - 実行結果の内容が回答に含まれているか\n"
            "   - 実行結果を無視していないか\n"
            "   - 誤った情報を伝えていないか\n\n"
            "3. **回答はユーザーの質問に適切に答えていますか？**\n"
            "   - 質問の意図を正しく理解しているか\n"
            "   - 必要な情報が全て含まれているか\n\n"
            "### 応答形式\n"
            "以下のJSONスキーマに厳密に従って応答してください:\n"
            f"```json\n{schema}```\n\n"
            "**重要事項**:\n"
            "- `success` は**すべての検証項目が合格**した場合のみ `true`\n"
            "- `reason` には検証結果の詳細な説明を記載\n"
            "- `suggestion` は失敗時のみ具体的な改善提案を記載（成功時は空文字 \"\"）\n"
            "- COEIROINKフィールドは**一切含めないでください**\n"
            "- JSON以外のテキストは一切出力しないでください\n"
        )

    def _process_bash_actions(self, actions: list) -> list:
        """
        bashActionsを処理し、実行結果を返す

        Args:
            actions: bashActions配列

        Returns:
            実行結果の配列 [{"command": str, "result": dict, "error": Optional[str]}]
        """
        if not self.bash_executor:
            self.logger.warning("BashExecutor未初期化のためbashActionsをスキップ")
            return []

        results = []
        for action in actions:
            if not isinstance(action, dict):
                continue

            command = action.get("command", "")
            reason = action.get("reason", "")

            if not command:
                continue

            self.logger.info(f"Executing bash command: {command} (reason: {reason})")

            try:
                result = self.bash_executor.execute(command)
                results.append(
                    {"command": command, "reason": reason, "result": result, "error": None}
                )
                self.logger.info(
                    f"Command executed successfully: {command} (exit_code: {result['exit_code']})"
                )

            except Exception as e:
                self.logger.error(f"Bash execution failed: {command} - {e}")
                results.append(
                    {"command": command, "reason": reason, "result": None, "error": str(e)}
                )

        return results

    def _format_bash_results(self, results: list) -> str:
        """
        BASH実行結果を人間可読な形式に整形

        Args:
            results: _process_bash_actions()の返却値

        Returns:
            整形されたテキスト
        """
        formatted = []
        for r in results:
            cmd = r["command"]
            reason = r.get("reason", "")

            if r["error"]:
                formatted.append(
                    f"❌ コマンド: {cmd}\n   理由: {reason}\n   エラー: {r['error']}"
                )
            else:
                result = r["result"]
                stdout = result["stdout"].strip() if result["stdout"] else "(出力なし)"
                stderr = result["stderr"].strip() if result["stderr"] else "(エラー出力なし)"

                # 出力が長い場合は切り詰め
                max_output_len = 1000
                if len(stdout) > max_output_len:
                    stdout = stdout[:max_output_len] + "\n... (省略)"
                if len(stderr) > max_output_len:
                    stderr = stderr[:max_output_len] + "\n... (省略)"

                formatted.append(
                    f"✅ コマンド: {cmd}\n"
                    f"   理由: {reason}\n"
                    f"   終了コード: {result['exit_code']}\n"
                    f"   作業ディレクトリ: {result['cwd']}\n"
                    f"   標準出力:\n{stdout}\n"
                    f"   標準エラー出力:\n{stderr}"
                )

        return "\n\n".join(formatted)

    def _bash_step2_generate_response(
        self, user_message: str, bash_results: list
    ) -> dict:
        """
        3段階フロー - ステップ2: BASH実行結果を踏まえた回答生成

        Args:
            user_message: ユーザーの質問
            bash_results: _process_bash_actions()の結果

        Returns:
            LLM応答（COEIROINKフィールドのみ、bashActions除外）
        """
        # Step 2専用プロンプトを使用
        step2_prompt = self._build_step2_prompt(user_message, bash_results)

        self.conversation_history.append({
            "role": "system",
            "content": step2_prompt
        })

        # Step 2用のJSON応答を要求（bashActions不要）
        response = self.ollama_client.chat(
            messages=self.conversation_history,
            stream=False,
            return_json=True
        )

        # Step 2のシステムメッセージとアシスタント応答を削除（履歴汚染防止）
        self.conversation_history.pop()  # システムメッセージを削除

        self.logger.info("BASH Step 2: Response generated based on execution results")
        return response

    def _bash_step3_verify(
        self, user_message: str, bash_results: list, response: dict
    ) -> dict:
        """
        3段階フロー - ステップ3: タスク達成度と回答の整合性を検証

        Args:
            user_message: ユーザーの質問
            bash_results: BASH実行結果
            response: ステップ2で生成した回答

        Returns:
            {"success": bool, "reason": str, "suggestion": str}
        """
        # Step 3専用プロンプトを使用
        step3_prompt = self._build_step3_prompt(user_message, bash_results, response)

        self.conversation_history.append({
            "role": "system",
            "content": step3_prompt
        })

        # Step 3用のJSON応答を要求（検証結果のみ）
        verification = self.ollama_client.chat(
            messages=self.conversation_history,
            stream=False,
            return_json=True
        )

        # 検証結果を履歴から削除（次回に影響させない）
        self.conversation_history.pop()

        self.logger.info(
            f"BASH Step 3: Verification result - success: {verification.get('success', False)}"
        )
        return verification

    def _execute_bash_workflow(
        self,
        user_message: str,
        initial_response: dict,
        max_retry: int = 2,
        enable_verification: bool = True
    ) -> dict:
        """
        3段階BASHワークフローを実行
        
        Args:
            user_message: ユーザーの質問
            initial_response: ステップ1のLLM応答
            max_retry: 最大再試行回数
            enable_verification: 検証ステップを有効化
        
        Returns:
            最終的なLLM応答
        """
        bash_actions = initial_response.get("bashActions", [])
        
        # BASHコマンドが不要な場合はそのまま返す
        if not bash_actions or not isinstance(bash_actions, list) or not self.bash_executor:
            return initial_response
        
        retry_count = 0
        current_response = initial_response
        
        while retry_count <= max_retry:
            # ステップ1で既にコマンドは生成されているので、実行のみ
            bash_results = self._process_bash_actions(bash_actions)
            
            if not bash_results:
                # 実行結果がない場合はそのまま返す
                return current_response
            
            # ステップ2: 実行結果を踏まえた回答生成
            step2_response = self._bash_step2_generate_response(user_message, bash_results)
            
            # 検証が無効な場合はステップ2の結果を返す
            if not enable_verification:
                self.logger.info("BASH workflow completed (verification disabled)")
                return step2_response
            
            # ステップ3: 検証
            verification = self._bash_step3_verify(user_message, bash_results, step2_response)
            
            if verification.get("success", False):
                # 検証成功
                self.logger.info(f"BASH workflow succeeded (attempt {retry_count + 1})")
                return step2_response
            
            # 検証失敗
            retry_count += 1
            reason = verification.get("reason", "不明なエラー")
            suggestion = verification.get("suggestion", "")
            
            self.logger.warning(
                f"BASH verification failed (attempt {retry_count}/{max_retry + 1}): {reason}"
            )
            
            if retry_count <= max_retry:
                # 再試行用のフィードバックを追加
                self.conversation_history.append({
                    "role": "system",
                    "content": (
                        f"前回のアプローチは失敗しました。\n"
                        f"理由: {reason}\n"
                        f"改善提案: {suggestion}\n"
                        "別のコマンドまたはアプローチを試してください。"
                    )
                })
                
                # 再度ステップ1から（新しいコマンドを生成）
                retry_response = self.ollama_client.chat(
                    messages=self.conversation_history,
                    stream=False,
                    return_json=True
                )
                
                bash_actions = retry_response.get("bashActions", [])
                if not bash_actions:
                    # コマンドが生成されなかった場合は失敗として扱う
                    self.logger.warning("No bash actions generated in retry")
                    break
                
                current_response = retry_response
        
        # 最大試行回数超過
        self.logger.error(f"BASH workflow failed after {max_retry + 1} attempts")
        return {
            **step2_response,
            "text": f"申し訳ございません。タスクの実行に失敗しました。理由: {reason}"
        }


    def _extract_voice_plan(self, response: Any) -> Optional[Dict[str, Any]]:
        """OllamaからのJSONレスポンスを検証し、音声合成に必要な形式へ変換"""
        if not isinstance(response, dict):
            self.logger.error("レスポンスが辞書形式ではありません")
            return None

        required_keys = [
            "text",
            "speakerUuid",
            "styleId",
            "speedScale",
            "volumeScale",
            "pitchScale",
            "intonationScale",
            "prePhonemeLength",
            "postPhonemeLength",
            "outputSamplingRate",
            "prosodyDetail",
        ]

        missing = [key for key in required_keys if key not in response]
        if missing:
            self.logger.error(f"レスポンスに必要なキーが不足: {missing}")
            return None

        try:
            voice_plan = {
                "text": str(response["text"]),
                "speakerUuid": str(response["speakerUuid"]),
                "styleId": int(response["styleId"]),
                "speedScale": float(response["speedScale"]),
                "volumeScale": float(response["volumeScale"]),
                "pitchScale": float(response["pitchScale"]),
                "intonationScale": float(response["intonationScale"]),
                "prePhonemeLength": float(response["prePhonemeLength"]),
                "postPhonemeLength": float(response["postPhonemeLength"]),
                "outputSamplingRate": int(response["outputSamplingRate"]),
                "prosodyDetail": response.get("prosodyDetail") or [],
            }
        except (TypeError, ValueError) as err:
            self.logger.error(f"レスポンスの型変換に失敗: {err}")
            return None

        return voice_plan

    def _synthesize_and_optionally_play(
        self, voice_plan: Dict[str, Any], play_audio: bool = True
    ) -> Optional[Path]:
        """COEIROINKで音声を合成し、必要に応じて再生"""
        if not self.coeiro_client:
            self.logger.error("COEIROINKクライアントが初期化されていません")
            return None

        speaker = self._find_speaker_by_uuid(voice_plan["speakerUuid"])
        if not speaker:
            self.logger.error(
                f"スピーカーUUIDが一致しません: {voice_plan['speakerUuid']}"
            )
            return None

        style_name = self._resolve_style_name(speaker, voice_plan["styleId"])
        if style_name is None:
            self.logger.error(
                f"スタイルID {voice_plan['styleId']} はスピーカー {speaker.speaker_name} に存在しません"
            )
            return None

        parameters = VoiceParameters(
            speed_scale=voice_plan["speedScale"],
            volume_scale=voice_plan["volumeScale"],
            pitch_scale=voice_plan["pitchScale"],
            intonation_scale=voice_plan["intonationScale"],
            pre_phoneme_length=voice_plan["prePhonemeLength"],
            post_phoneme_length=voice_plan["postPhonemeLength"],
            output_sampling_rate=voice_plan["outputSamplingRate"],
        )
        parameters.validate()

        audio_path = self._prepare_output_path()

        audio_bytes = self.coeiro_client.synthesize(
            text=voice_plan["text"],
            speaker_name=speaker.speaker_name,
            style_name=style_name,
            parameters=parameters,
            use_prosody=bool(voice_plan["prosodyDetail"]),
            prosody_detail=voice_plan.get("prosodyDetail"),
            output_path=audio_path,
        )

        if not audio_bytes:
            self.logger.error("音声データが生成されませんでした")
            return None

        if play_audio and self.audio_player:
            try:
                self.audio_player.play_wav(str(audio_path))
            except Exception as exc:  # pragma: no cover - 実行環境依存
                self.logger.error(f"音声再生に失敗: {exc}")
        elif play_audio and not self.audio_player:
            self.logger.warning("AudioPlayerが利用できないため再生をスキップします")

        self.last_audio_path = audio_path
        return audio_path

    def _prepare_output_path(self) -> Path:
        """音声ファイルの保存先パスを生成"""
        timestamp = int(time.time() * 1000)
        filename = f"response_{timestamp}.wav"
        return self.audio_output_dir / filename

    def _find_speaker_by_uuid(self, speaker_uuid: str) -> Optional[Speaker]:
        """UUIDからスピーカー情報を取得"""
        if not self.coeiro_client:
            return None
        for speaker in self.coeiro_client.speakers.values():
            if speaker.speaker_uuid == speaker_uuid:
                return speaker
        return None

    @staticmethod
    def _resolve_style_name(speaker: Speaker, style_id: int) -> Optional[str]:
        """スタイルIDからスタイル名を取得"""
        for style in speaker.styles:
            if style.get("styleId") == style_id:
                return style.get("styleName")
        return None

    def _request_bash_approval(self, command: str, reason: str) -> bool:
        """
        BASHコマンドの承認をリクエスト（Human-in-the-Loop）

        Args:
            command: 実行するコマンド
            reason: 実行理由

        Returns:
            承認された場合True、拒否された場合False
        """
        try:
            # BashApprovalQueueをインポート
            from ..server.app import get_bash_approval_queue
            import asyncio
            import threading

            queue = get_bash_approval_queue()

            # 承認リクエストを追加
            request_id = queue.add_request(command, reason)
            self.logger.info(
                f"BASH承認リクエスト送信: {request_id} - command: {command}, reason: {reason}"
            )

            # 承認待機（最大5分）
            approved = queue.wait_for_approval(request_id, timeout=300.0)

            if approved:
                self.logger.info(f"BASH承認されました: {command}")
            else:
                self.logger.warning(f"BASH拒否されました: {command}")

            return approved

        except Exception as e:
            self.logger.error(f"BASH承認リクエストに失敗: {e}")
            # エラー時はデフォルトで拒否
            return False
