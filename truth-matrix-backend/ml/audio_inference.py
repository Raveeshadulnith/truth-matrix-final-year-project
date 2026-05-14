from __future__ import annotations

from typing import Dict, Union

from ml.model_common import ModelNotAvailableError


def analyze_audio(_audio_path: str) -> Dict[str, Union[str, float]]:
    raise ModelNotAvailableError(
        "Audio analysis is not connected yet because the trained audio model is still in progress."
    )
