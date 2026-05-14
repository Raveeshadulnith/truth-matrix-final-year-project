import random
from typing import Dict, Union

LABELS = ["Authentic", "Suspected Deepfake"]


def analyze_image(image_path: str) -> Dict[str, Union[str, float, None]]:
    """
    Temporary image inference function.

    Later, replace this dummy logic with your trained image deepfake model.
    """
    label = random.choice(LABELS)
    confidence = round(random.uniform(75, 98), 2)

    return {
        "media_type": "image",
        "label": label,
        "confidence": confidence,
        "explanation": "Temporary dummy result. Replace this with trained image model prediction later.",
        "heatmap_url": None,
    }
