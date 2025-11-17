"""Bash workflow support for :mod:`ai_secretary`."""

from __future__ import annotations

from typing import Any, Dict, List

from ..system_prompt_loader import SystemPromptLoader


class BashWorkflowMixin:
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

        # 外部ファイルからプロンプトテンプレートを読み込み
        loader = SystemPromptLoader()
        return loader.format(
            "bash/layer0_bash_instruction.txt",
            commands_preview=commands_preview,
            root_dir=self.bash_executor.root_dir,
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

        # 外部ファイルからプロンプトテンプレートを読み込み
        loader = SystemPromptLoader()
        return loader.format(
            "bash/layer1_step2_response.txt",
            user_message=user_message,
            result_context=result_context,
            schema=schema,
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
        # BASH実行結果の詳細なサマリー（stdout/stderr含む）
        bash_summary_parts = []
        for i, r in enumerate(bash_results, 1):
            part = f"【コマンド{i}】\n"
            part += f"  コマンド: `{r['command']}`\n"

            if r['result']:
                part += f"  終了コード: {r['result']['exit_code']}\n"

                stdout = r['result'].get('stdout', '').strip()
                stderr = r['result'].get('stderr', '').strip()

                if stdout:
                    part += f"  標準出力:\n{stdout}\n"
                else:
                    part += f"  標準出力: (なし)\n"

                if stderr:
                    part += f"  標準エラー:\n{stderr}\n"
                else:
                    part += f"  標準エラー: (なし)\n"
            else:
                part += f"  実行結果: エラー\n"
                part += f"  エラー詳細: {r.get('error', '不明なエラー')}\n"

            bash_summary_parts.append(part)

        bash_summary = "\n".join(bash_summary_parts)
        schema = self._get_step3_json_schema()

        # 外部ファイルからプロンプトテンプレートを読み込み
        loader = SystemPromptLoader()
        return loader.format(
            "bash/layer2_step3_verification.txt",
            user_message=user_message,
            bash_summary=bash_summary,
            response_text=response.get('text', ''),
            schema=schema,
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

        # デバッグ: 検証レスポンスの全体を出力
        self.logger.debug(f"BASH Step 3: Raw verification response: {verification}")

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
            from ...server.dependencies import get_bash_approval_queue
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
