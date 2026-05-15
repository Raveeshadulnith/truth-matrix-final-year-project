import random
from typing import Dict, Union

LABELS = ["Authentic", "Suspected Deepfake"]


def analyze_audio(audio_path: str) -> Dict[str, Union[str, float]]:
    """
    Temporary audio inference function.

    Later, replace this dummy logic with your trained audio deepfake model.
    """
    label = random.choice(LABELS)
    confidence = round(random.uniform(70, 95), 2)

    return {
        "media_type": "audio",
        "label": label,
        "confidence": confidence,
        "explanation": "Temporary dummy result. Replace this with trained audio model prediction later.",
    }
