import random
from typing import Dict, Union

LABELS = ["Authentic", "Suspected Deepfake"]


def analyze_video(video_path: str) -> Dict[str, Union[str, float, int, None]]:
    """
    Temporary video inference function.

    Later, replace this dummy logic with frame extraction and your trained video model.
    """
    label = random.choice(LABELS)
    confidence = round(random.uniform(70, 96), 2)

    return {
        "media_type": "video",
        "label": label,
        "confidence": confidence,
        "frames_analyzed": 16,
        "explanation": "Temporary dummy result. Replace this with trained video model prediction later.",
        "heatmap_url": None,
    }
