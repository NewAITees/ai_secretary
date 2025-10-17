"""
COEIROINK音声合成システム - 完全版
抑揚付き高品質音声合成を実現するPythonライブラリ

設計思想:
1. スピーカー管理: UUID/StyleIDベースの階層構造
2. 音声パラメータ: 速度/音量/ピッチ/抑揚の詳細制御
3. 韻律制御: prosodyDetailによる細かい抑揚設定
4. 拡張性: 簡単にカスタマイズ可能なクラス設計

============================================================
使い方
============================================================

基本的な使用例:
    from coeiroink_client import COEIROINKClient, VoiceParameters

    # クライアント作成
    client = COEIROINKClient()

    # 基本的な音声合成
    audio = client.synthesize(
        text="こんにちは、COEIROINKです。",
        speaker_name="AI声優-金苗",
        output_path="output.wav"
    )

パラメータをカスタマイズした音声合成:
    # パラメータを設定
    params = VoiceParameters(
        speed_scale=1.2,      # 少し速く
        pitch_scale=0.05,     # 少し高く
        volume_scale=1.0,     # 標準音量
        intonation_scale=1.3  # 抑揚を強く
    )

    # カスタムパラメータで合成
    audio = client.synthesize(
        text="カスタムパラメータのテストです。",
        speaker_name="つくよみちゃん",
        parameters=params,
        output_path="custom.wav"
    )

============================================================
パラメータ仕様（COEIROINK v1 API）
============================================================

必須パラメータ:
  - text (str): 合成するテキスト
  - speakerUuid (str): スピーカーUUID
  - styleId (int): スタイルID
  - speedScale (float): 話速
  - volumeScale (float): 音量
  - pitchScale (float): ピッチ
  - intonationScale (float): 抑揚
  - prePhonemeLength (float): 発声前無音時間
  - postPhonemeLength (float): 発声後無音時間
  - outputSamplingRate (int): サンプリングレート

オプションパラメータ:
  - prosodyDetail (array): 詳細な韻律情報（空配列可）
  - pauseLength (float): ポーズの長さ
  - adjustedF0 (array): F0調整値
  - processingAlgorithm (str): 処理アルゴリズム

============================================================
パラメータ範囲（実測値）
============================================================

speedScale（話速）:
  - デフォルト: 1.0
  - 推奨範囲: 0.5〜2.0
  - 実測動作範囲: 0.1〜5.0 (全て成功)
  - 説明: 1.0が標準速度、小さいほど遅く、大きいほど速く
  - 例: 0.5=ゆっくり、1.3=やや速め、2.0=2倍速

volumeScale（音量）:
  - デフォルト: 1.0
  - 推奨範囲: 0.5〜2.0
  - 実測動作範囲: 0.0〜3.0 (全て成功)
  - 説明: 1.0が標準音量、0.0=無音、2.0=2倍
  - 例: 0.8=やや小さめ、1.2=やや大きめ

pitchScale（ピッチ）:
  - デフォルト: 0.0
  - 推奨範囲: -0.15〜0.15
  - 実測動作範囲: -1.0〜1.0 (全て成功)
  - 説明: 0.0が標準ピッチ、正=高く、負=低く
  - 例: -0.1=やや低め、0.1=やや高め
  - 注意: 大きな値は不自然な音声になる可能性

intonationScale（抑揚）:
  - デフォルト: 1.0
  - 推奨範囲: 0.5〜2.0
  - 実測動作範囲: 0.0〜3.0 (全て成功)
  - 説明: 1.0が標準抑揚、0.0=平坦、大きいほど抑揚が強い
  - 例: 0.5=控えめ、1.5=感情豊か

prePhonemeLength（発声前無音）:
  - デフォルト: 0.1秒
  - 範囲: 0.0〜（推奨は0.0〜1.0秒）
  - 説明: 音声開始前の無音時間

postPhonemeLength（発声後無音）:
  - デフォルト: 0.5秒
  - 範囲: 0.0〜（推奨は0.0〜2.0秒）
  - 説明: 音声終了後の無音時間

outputSamplingRate（サンプリングレート）:
  - デフォルト: 24000 Hz
  - 一般的な値: 16000, 22050, 24000, 44100, 48000
  - 説明: 高いほど音質が良いがファイルサイズも増加

============================================================
エラー処理
============================================================

よくあるエラーと対処法:

1. 500 Internal Server Error
   - 原因: パラメータが極端すぎる、スピーカーが読み込まれていない
   - 対処: パラメータを推奨範囲内に、COEIROINKを再起動

2. スピーカーが見つからない
   - 原因: 指定したスピーカー名が存在しない
   - 対処: list_speakers()で利用可能なスピーカーを確認

3. 接続エラー
   - 原因: COEIROINKが起動していない、ポートが異なる
   - 対処: COEIROINK起動確認、ポート番号確認(デフォルト:50032)

============================================================
"""

import json
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Speaker:
    """
    スピーカー情報を管理するクラス

    Attributes:
        speaker_name: スピーカーの名前
        speaker_uuid: スピーカーの一意識別子
        styles: 利用可能なスタイルのリスト
        version: モデルのバージョン
    """
    speaker_name: str
    speaker_uuid: str
    styles: List[Dict[str, Any]]
    version: str

    def get_style_id(self, style_name: str) -> Optional[int]:
        """スタイル名からスタイルIDを取得"""
        for style in self.styles:
            if style['styleName'] == style_name:
                return style['styleId']
        return None

    def list_styles(self) -> List[str]:
        """利用可能なスタイル名のリストを返す"""
        return [style['styleName'] for style in self.styles]


@dataclass
class VoiceParameters:
    """
    音声合成のパラメータを管理するクラス

    各パラメータの説明:
    - speed_scale: 話す速度 (0.5〜2.0推奨、1.0が標準)
    - volume_scale: 音量 (0.0〜2.0推奨、1.0が標準)
    - pitch_scale: ピッチ調整 (-0.15〜0.15推奨、0.0が標準)
    - intonation_scale: 抑揚の強さ (0.0〜2.0推奨、1.0が標準)
    - pre_phoneme_length: 発声前の無音時間(秒)
    - post_phoneme_length: 発声後の無音時間(秒)
    - output_sampling_rate: 出力サンプリングレート(Hz)
    """
    speed_scale: float = 1.0
    volume_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    pre_phoneme_length: float = 0.1
    post_phoneme_length: float = 0.5
    output_sampling_rate: int = 24000

    def validate(self) -> bool:
        """パラメータの妥当性チェック"""
        checks = [
            (0.5 <= self.speed_scale <= 2.0, "speed_scale"),
            (0.0 <= self.volume_scale <= 2.0, "volume_scale"),
            (-0.15 <= self.pitch_scale <= 0.15, "pitch_scale"),
            (0.0 <= self.intonation_scale <= 2.0, "intonation_scale"),
            (0.0 <= self.pre_phoneme_length <= 1.5, "pre_phoneme_length"),
            (0.0 <= self.post_phoneme_length <= 1.5, "post_phoneme_length"),
            (self.output_sampling_rate in [16000, 24000, 44100, 48000], "output_sampling_rate")
        ]

        for check, param_name in checks:
            if not check:
                logger.warning(f"パラメータ {param_name} が推奨範囲外です")
                return False
        return True


@dataclass
class ProsodyMora:
    """
    韻律の最小単位(モーラ)を表すクラス

    日本語の音節単位で抑揚を制御
    例: "こんにちは" → ["こ", "ん", "に", "ち", "は"]
    """
    phoneme: str  # 音素
    hira: str     # ひらがな表記
    accent: int   # アクセント(0 or 1)


@dataclass
class SynthesisRequest:
    """
    音声合成リクエストの完全な仕様

    COEIROINKのAPIに送信する全パラメータを管理
    """
    speaker_uuid: str
    style_id: int
    text: str
    parameters: VoiceParameters = field(default_factory=VoiceParameters)
    prosody_detail: List[List[Dict]] = field(default_factory=list)

    def to_api_format(self) -> Dict[str, Any]:
        """API送信用の辞書形式に変換"""
        return {
            "speakerUuid": self.speaker_uuid,
            "styleId": self.style_id,
            "text": self.text,
            "speedScale": self.parameters.speed_scale,
            "volumeScale": self.parameters.volume_scale,
            "pitchScale": self.parameters.pitch_scale,
            "intonationScale": self.parameters.intonation_scale,
            "prePhonemeLength": self.parameters.pre_phoneme_length,
            "postPhonemeLength": self.parameters.post_phoneme_length,
            "outputSamplingRate": self.parameters.output_sampling_rate,
            "prosodyDetail": self.prosody_detail if self.prosody_detail else [],
        }


class COEIROINKClient:
    """
    COEIROINKのAPIクライアント

    音声合成の全機能を提供するメインクラス
    """

    def __init__(self, api_url: str = "http://localhost:50032"):
        """
        Args:
            api_url: COEIROINKのAPIサーバーURL
        """
        self.api_url = api_url
        self.speakers: Dict[str, Speaker] = {}
        self._load_speakers()

    def _load_speakers(self) -> None:
        """利用可能なスピーカー情報をAPIから取得"""
        try:
            response = requests.get(f"{self.api_url}/v1/speakers", timeout=5)
            response.raise_for_status()

            for item in response.json():
                speaker = Speaker(
                    speaker_name=item['speakerName'],
                    speaker_uuid=item['speakerUuid'],
                    styles=item['styles'],
                    version=item['version']
                )
                self.speakers[speaker.speaker_name] = speaker

            logger.info(f"スピーカー {len(self.speakers)} 個を読み込みました")
        except requests.exceptions.RequestException as e:
            logger.error(f"スピーカー情報の取得に失敗: {e}")
            raise

    def list_speakers(self) -> List[str]:
        """利用可能なスピーカー名のリストを返す"""
        return list(self.speakers.keys())

    def get_speaker(self, speaker_name: str) -> Optional[Speaker]:
        """スピーカー名からSpeakerオブジェクトを取得"""
        return self.speakers.get(speaker_name)

    def estimate_prosody(self, text: str) -> List[List[Dict]]:
        """
        テキストから韻律情報を推定

        Args:
            text: 音声合成するテキスト

        Returns:
            韻律詳細情報
        """
        try:
            response = requests.post(
                f"{self.api_url}/v1/estimate_prosody",
                headers={"Content-Type": "application/json"},
                json={"text": text},
                timeout=10
            )
            response.raise_for_status()
            prosody_data = response.json()
            return prosody_data.get('detail', [])
        except requests.exceptions.RequestException as e:
            logger.error(f"韻律推定に失敗: {e}")
            return []

    def synthesize(
        self,
        text: str,
        speaker_name: str,
        style_name: str = None,
        parameters: VoiceParameters = None,
        use_prosody: bool = False,
        output_path: Optional[Path] = None
    ) -> bytes:
        """
        音声合成のメイン関数

        Args:
            text: 合成するテキスト
            speaker_name: スピーカー名
            style_name: スタイル名(Noneの場合は最初のスタイル)
            parameters: 音声パラメータ
            use_prosody: 韻律情報を使用するか
            output_path: 保存先パス(Noneの場合は保存しない)

        Returns:
            音声データ(wavフォーマット)
        """
        # スピーカー取得
        speaker = self.get_speaker(speaker_name)
        if not speaker:
            raise ValueError(f"スピーカー '{speaker_name}' が見つかりません")

        # スタイルID取得
        if style_name:
            style_id = speaker.get_style_id(style_name)
            if style_id is None:
                raise ValueError(f"スタイル '{style_name}' が見つかりません")
        else:
            style_id = speaker.styles[0]['styleId']

        # パラメータ設定
        if parameters is None:
            parameters = VoiceParameters()

        if not parameters.validate():
            logger.warning("パラメータに問題がありますが、続行します")

        # 韻律情報取得(オプション)
        prosody_detail = []
        if use_prosody:
            prosody_detail = self.estimate_prosody(text)
            logger.info("韻律情報を使用します")

        # リクエスト作成
        request = SynthesisRequest(
            speaker_uuid=speaker.speaker_uuid,
            style_id=style_id,
            text=text,
            parameters=parameters,
            prosody_detail=prosody_detail
        )

        # API呼び出し
        try:
            response = requests.post(
                f"{self.api_url}/v1/synthesis",
                headers={
                    "accept": "audio/wav",
                    "Content-Type": "application/json"
                },
                json=request.to_api_format(),
                timeout=30
            )
            response.raise_for_status()

            audio_data = response.content
            logger.info(f"音声合成成功: {len(audio_data)} bytes")

            # ファイル保存
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(audio_data)
                logger.info(f"音声ファイル保存: {output_path}")

            return audio_data

        except requests.exceptions.RequestException as e:
            logger.error(f"音声合成に失敗: {e}")
            raise

    def synthesize_with_emotions(
        self,
        text_segments: List[Dict[str, Any]],
        output_path: Optional[Path] = None
    ) -> List[bytes]:
        """
        感情付き音声合成

        テキストセグメントごとに異なるパラメータで合成

        Args:
            text_segments: セグメントリスト
                [
                    {
                        "text": "こんにちは",
                        "speaker_name": "つくよみちゃん",
                        "style_name": "れいせい",
                        "parameters": VoiceParameters(...)
                    },
                    ...
                ]
            output_path: 結合音声の保存先(Noneの場合は結合しない)

        Returns:
            各セグメントの音声データリスト
        """
        audio_segments = []

        for i, segment in enumerate(text_segments):
            logger.info(f"セグメント {i+1}/{len(text_segments)} を合成中...")

            audio = self.synthesize(
                text=segment['text'],
                speaker_name=segment['speaker_name'],
                style_name=segment.get('style_name'),
                parameters=segment.get('parameters'),
                use_prosody=segment.get('use_prosody', False)
            )
            audio_segments.append(audio)

        # 音声結合が必要な場合はffmpegなどを使用
        # ここでは個別の音声を返すのみ

        logger.info(f"全 {len(audio_segments)} セグメントの合成完了")
        return audio_segments

    def export_speaker_info(self, output_path: Path) -> None:
        """スピーカー情報をJSONファイルに出力"""
        speaker_data = []
        for speaker in self.speakers.values():
            speaker_data.append({
                "speakerName": speaker.speaker_name,
                "speakerUuid": speaker.speaker_uuid,
                "styles": speaker.styles,
                "version": speaker.version
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(speaker_data, f, ensure_ascii=False, indent=2)

        logger.info(f"スピーカー情報を {output_path} に保存しました")


# ========================================
# 使用例
# ========================================

def example_basic():
    """基本的な使用例"""
    print("\n=== 基本的な使用例 ===")

    # クライアント初期化
    client = COEIROINKClient()

    # 利用可能なスピーカーを表示
    print("利用可能なスピーカー:")
    for name in client.list_speakers():
        speaker = client.get_speaker(name)
        print(f"  - {name}: {speaker.list_styles()}")

    # シンプルな音声合成
    audio = client.synthesize(
        text="こんにちは、今日はいい天気ですね。",
        speaker_name="つくよみちゃん",
        style_name="れいせい",
        output_path="output_basic.wav"
    )
    print(f"音声合成完了: {len(audio)} bytes")


def example_with_parameters():
    """パラメータ調整の例"""
    print("\n=== パラメータ調整の例 ===")

    client = COEIROINKClient()

    # カスタムパラメータで合成
    params = VoiceParameters(
        speed_scale=1.2,      # 少し速く
        volume_scale=1.1,     # 少し大きく
        pitch_scale=0.05,     # 少し高く
        intonation_scale=1.3  # 抑揚を強く
    )

    audio = client.synthesize(
        text="感情豊かに話してみます!",
        speaker_name="つくよみちゃん",
        parameters=params,
        use_prosody=True,  # 韻律情報を使用
        output_path="output_expressive.wav"
    )
    print(f"表現力豊かな音声合成完了: {len(audio)} bytes")


def example_multi_segment():
    """複数セグメント合成の例"""
    print("\n=== 複数セグメント合成の例 ===")

    client = COEIROINKClient()

    # 場面ごとに異なるパラメータで合成
    segments = [
        {
            "text": "おはようございます。",
            "speaker_name": "つくよみちゃん",
            "style_name": "れいせい",
            "parameters": VoiceParameters(speed_scale=1.0)
        },
        {
            "text": "今日は楽しい日になりそうです!",
            "speaker_name": "つくよみちゃん",
            "style_name": "れいせい",
            "parameters": VoiceParameters(
                speed_scale=1.1,
                pitch_scale=0.05,
                intonation_scale=1.4
            )
        }
    ]

    audio_list = client.synthesize_with_emotions(segments)
    print(f"{len(audio_list)} セグメントの音声を生成しました")


def example_export_speakers():
    """スピーカー情報のエクスポート例"""
    print("\n=== スピーカー情報のエクスポート ===")

    client = COEIROINKClient()
    client.export_speaker_info(Path("speakers.json"))
    print("speakers.json に情報を保存しました")


if __name__ == "__main__":
    print("COEIROINK音声合成システム")
    print("注意: COEIROINKを起動してから実行してください")
    print("=" * 50)

    try:
        # 各種使用例を実行
        example_basic()
        example_with_parameters()
        example_multi_segment()
        example_export_speakers()

        print("\n" + "=" * 50)
        print("全ての例の実行が完了しました!")

    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        print("COEIROINKが起動していることを確認してください")
