# COEIROINK API調査結果

## 調査日時
2025-10-17

## 調査内容

### 1. API 500エラーの原因調査

インターネット調査により以下の情報を入手：

### 2. 正しいAPI形式

#### 必須ヘッダー
```
accept: audio/wav
Content-Type: application/json
```

#### リクエストボディの必須パラメータ
- `speakerUuid`: スピーカーID
- `styleId`: スタイルID
- `text`: 合成するテキスト
- `volumeScale`: 音量（デフォルト: 1）
- `pitchScale`: ピッチ（デフォルト: 0）
- `intonationScale`: 抑揚（デフォルト: 1）
- `speedScale`: 速度（デフォルト: 1）
- `prePhonemeLength`: 前無音（デフォルト: 0）
- `postPhonemeLength`: 後無音（デフォルト: 0）
- `outputSamplingRate`: サンプリングレート（例: 44100）
- `prosodyDetail`: 韻律詳細（空配列可: `[]`）

#### オプションパラメータ
- `adjustedF0`: F0調整（空配列可: `[]`）
- `processingAlgorithm`: 処理アルゴリズム（例: "coeiroink"）
- `startTrimBuffer`: 開始トリムバッファ（デフォルト: 0）
- `endTrimBuffer`: 終了トリムバッファ（デフォルト: 0）
- `sampledIntervalValue`: サンプル間隔値（デフォルト: 0）

### 3. Python実装例

```python
import requests
import json

COEIROINK_URL = "http://localhost:50032/v1/synthesis"
SPEAKER_UUID = "3c37646f-3881-5374-2a83-149267990abc"

payload = {
    "speakerUuid": SPEAKER_UUID,
    "styleId": 0,
    "text": "今日はいい天気ですね",
    "speedScale": 1.0,
    "volumeScale": 1.0,
    "prosodyDetail": [],
    "pitchScale": 0.0,
    "intonationScale": 1.0,
    "prePhonemeLength": 0.1,
    "postPhonemeLength": 0.5,
    "outputSamplingRate": 24000
}

headers = {
    "accept": "audio/wav",
    "Content-Type": "application/json"
}

response = requests.post(
    COEIROINK_URL,
    headers=headers,
    data=json.dumps(payload)
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

### 4. 判明した問題点

1. **ヘッダーに`accept`が必要**: 当初のコードでは`accept`ヘッダーがなかった
2. **prosodyDetailは空配列でも可**: 韻律情報が不要な場合は空配列`[]`でOK

### 5. 修正内容

- `src/coeiroink_client/client.py`の`synthesize`メソッドにて：
  - ヘッダーに`accept: audio/wav`を追加
  - `prosodyDetail`が空の場合は明示的に空配列を設定

### 6. 現在の状況

- コード修正完了
- テスト未実施（COEIROINKが正しく起動している必要がある）

### 7. 次のステップ

COEIROINKが正しく起動し、スピーカーモデルが読み込まれている状態で再度テストが必要。

## 参考リンク

- [COEIROINK公式ヘルプ](https://coeiroink.com/help/031)
- [COEIROINK API使用例（Zenn）](https://zenn.dev/hk03ne/articles/ca4f76ea94bb26)
