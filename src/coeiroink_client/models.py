"""Data models for the COEIROINK client."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Speaker:
    """COEIROINK speaker metadata."""

    speaker_name: str
    speaker_uuid: str
    styles: List[Dict[str, Any]]
    version: str

    def get_style_id(self, style_name: str) -> Optional[int]:
        """Return styleId for the provided style name."""
        for style in self.styles:
            if style["styleName"] == style_name:
                return style["styleId"]
        return None

    def list_styles(self) -> List[str]:
        """Return all style names available for the speaker."""
        return [style["styleName"] for style in self.styles]


@dataclass
class VoiceParameters:
    """Voice synthesis parameters with simple validation helpers."""

    speed_scale: float = 1.0
    volume_scale: float = 1.0
    pitch_scale: float = 0.0
    intonation_scale: float = 1.0
    pre_phoneme_length: float = 0.1
    post_phoneme_length: float = 0.5
    output_sampling_rate: int = 24000

    def validate(self) -> bool:
        """Return True if all parameters fall inside recommended ranges."""
        checks = [
            (0.5 <= self.speed_scale <= 2.0, "speed_scale"),
            (0.0 <= self.volume_scale <= 2.0, "volume_scale"),
            (-0.15 <= self.pitch_scale <= 0.15, "pitch_scale"),
            (0.0 <= self.intonation_scale <= 2.0, "intonation_scale"),
            (0.0 <= self.pre_phoneme_length <= 1.5, "pre_phoneme_length"),
            (0.0 <= self.post_phoneme_length <= 1.5, "post_phoneme_length"),
            (
                self.output_sampling_rate in [16000, 24000, 44100, 48000],
                "output_sampling_rate",
            ),
        ]

        for check, param in checks:
            if not check:
                logger.warning("パラメータ %s が推奨範囲外です", param)
                return False
        return True


@dataclass
class ProsodyMora:
    """Prosody unit (mora) representation."""

    phoneme: str
    hira: str
    accent: int


@dataclass
class SynthesisRequest:
    """Complete set of parameters used for API calls."""

    speaker_uuid: str
    style_id: int
    text: str
    parameters: VoiceParameters = field(default_factory=VoiceParameters)
    prosody_detail: List[List[Dict]] = field(default_factory=list)

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to the payload structure expected by COEIROINK."""
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
