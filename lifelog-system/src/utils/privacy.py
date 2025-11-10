"""
Privacy utility functions for lifelog-system.

Design: Privacy-by-design - デフォルトで個人情報を保存しない
"""

import hashlib
import re
from typing import Optional


def stable_hash(s: str) -> str:
    """
    安定したハッシュ値を生成（プライバシー保護）.

    Args:
        s: ハッシュ化する文字列

    Returns:
        SHA256ハッシュ（16文字）
    """
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def extract_domain_if_browser(title: str, process_name: str) -> Optional[str]:
    """
    ブラウザの場合のみドメイン（eTLD+1）を抽出.

    フルURLは保存しない。

    Args:
        title: ウィンドウタイトル
        process_name: プロセス名

    Returns:
        ドメイン（ブラウザ以外の場合はNone）
    """
    browsers = ["chrome.exe", "firefox.exe", "msedge.exe", "brave.exe", "chrome", "firefox"]
    if process_name.lower() not in browsers:
        return None

    # 簡易実装：タイトルからドメイン部分を推定
    match = re.search(r"([a-zA-Z0-9-]+\.[a-zA-Z]{2,})", title)
    return match.group(1) if match else None


def is_sensitive_process(process_name: str, sensitive_keywords: list[str]) -> bool:
    """
    センシティブなプロセスか判定.

    Args:
        process_name: プロセス名
        sensitive_keywords: センシティブキーワードリスト

    Returns:
        センシティブな場合True
    """
    process_lower = process_name.lower()
    for keyword in sensitive_keywords:
        if keyword.lower() in process_lower:
            return True
    return False
