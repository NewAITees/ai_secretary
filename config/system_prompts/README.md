# System Prompts

このディレクトリには、AI Secretaryの各機能で使用するシステムプロンプトテンプレートが格納されています。

## ディレクトリ構造

```
config/system_prompts/
├── bash/                                   # BASH実行機能用プロンプト
│   ├── layer0_bash_instruction.txt        # Layer 0: BASH機能の説明とコマンドリスト
│   ├── layer1_step2_response.txt          # Layer 1: BASH実行結果を踏まえた回答生成
│   └── layer2_step3_verification.txt      # Layer 2: 検証専用モード
└── README.md                              # このファイル
```

## BASH実行機能の三層構造

### Layer 0: BASH機能の説明 (layer0_bash_instruction.txt)
- **用途**: 通常の会話でBASH実行機能を利用可能にする
- **変数置換**:
  - `{commands_preview}`: 利用可能なコマンドのリスト
  - `{root_dir}`: ルートディレクトリパス
- **出力**: `bashActions` 配列を含むJSON応答

### Layer 1: BASH実行結果を踏まえた回答生成 (layer1_step2_response.txt)
- **用途**: BASH実行後、その結果を踏まえた回答を生成
- **変数置換**:
  - `{user_message}`: ユーザーの元の質問
  - `{result_context}`: BASH実行結果のサマリー
  - `{schema}`: 応答用JSONスキーマ
- **出力**: `bashActions` を含まないJSON応答

### Layer 2: 検証専用モード (layer2_step3_verification.txt)
- **用途**: Step 2で生成した回答を検証
- **変数置換**:
  - `{user_message}`: ユーザーの元の質問
  - `{bash_summary}`: BASH実行結果の詳細（stdout/stderr含む）
  - `{response_text}`: Step 2で生成した回答テキスト
  - `{schema}`: 検証結果用JSONスキーマ
- **出力**: `{"success": bool, "reason": str, "suggestion": str}` のみ

## プロンプトの編集

各`.txt`ファイルを直接編集することで、AIの動作をカスタマイズできます。
変数（`{variable_name}`形式）は実行時に自動的に置換されます。

## 新しいプロンプトの追加

1. 適切なサブディレクトリに`.txt`ファイルを作成
2. 必要に応じて変数を`{variable_name}`形式で埋め込む
3. コード側で対応する読み込み処理を実装
