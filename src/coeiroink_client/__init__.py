"""COEIROINK client toolkit.

詳細な使い方は ``doc/COEIROINK_CLIENT_OVERVIEW.md`` を参照してください。
"""

from .client import COEIROINKClient
from .models import ProsodyMora, Speaker, SynthesisRequest, VoiceParameters

__all__ = [
    "COEIROINKClient",
    "ProsodyMora",
    "Speaker",
    "SynthesisRequest",
    "VoiceParameters",
]
