"""Utility script to download YouTube transcripts using youtube-transcript-api.

使い方:
    # 基本的な使用方法（動画IDを指定）
    uv run python scripts/download_transcript.py VIDEO_ID

    # YouTubeのURLを直接指定
    uv run python scripts/download_transcript.py https://youtu.be/VIDEO_ID
    uv run python scripts/download_transcript.py https://www.youtube.com/watch?v=VIDEO_ID

    # 言語の優先順位を指定（デフォルト: ja en）
    uv run python scripts/download_transcript.py VIDEO_ID -l ja en ko

    # 出力ファイルのパスを指定（デフォルト: outputs/transcripts/{video_id}.txt）
    uv run python scripts/download_transcript.py VIDEO_ID -o /path/to/output.txt

add_argumentの説明:
    add_argumentは、コマンドライン引数（このスクリプトを実行する時に渡すオプション）の
    定義です。「このスクリプトを使いたい人がどんな引数を渡せるか」を設定しています。

    - "video": 必須の引数。YouTube動画のIDまたはURL
    - "-l", "--languages": オプション引数。字幕の言語優先順位（複数指定可）
    - "-o", "--output": オプション引数。出力ファイルのパス

    helpパラメータは、ユーザーが --help を実行した時に表示される説明文です。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    YouTubeTranscriptApiException,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the transcript for a YouTube video and save it as text."
    )
    parser.add_argument(
        "video",
        help="YouTube video ID or URL (e.g. https://youtu.be/VIDEO_ID)",
    )
    parser.add_argument(
        "-l",
        "--languages",
        nargs="+",
        default=("ja", "en"),
        help="Transcript language preference order (default: ja en).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Path to the output text file. Defaults to outputs/transcripts/{video_id}.txt",
    )
    return parser.parse_args()


def extract_video_id(value: str) -> str:
    if "://" not in value:
        return value.strip()

    parsed = urlparse(value)
    if parsed.hostname in {"youtu.be"} and parsed.path:
        return parsed.path.lstrip("/")

    if parsed.hostname and "youtube" in parsed.hostname:
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        if video_id:
            return video_id

    raise ValueError(f"Unable to extract video ID from: {value}")


def transcript_to_text(snippets: Iterable) -> str:
    lines: list[str] = []
    for snippet in snippets:
        text = getattr(snippet, "text", "").strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def main() -> int:
    args = parse_arguments()

    try:
        video_id = extract_video_id(args.video)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    output_path = args.output
    if output_path is None:
        output_path = Path("outputs") / "transcripts" / f"{video_id}.txt"

    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=tuple(args.languages))
    except YouTubeTranscriptApiException as exc:
        print(f"Failed to fetch transcript for {video_id}: {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = transcript_to_text(transcript.snippets)
    output_path.write_text(text, encoding="utf-8")

    print(f"Saved transcript to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
