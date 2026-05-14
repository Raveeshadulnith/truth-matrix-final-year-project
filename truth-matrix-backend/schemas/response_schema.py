from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


PredictionLabel = Literal["Authentic", "Suspected Deepfake"]
MediaType = Literal["image", "video", "audio"]


class ImageUrlRequest(BaseModel):
    image_url: str = Field(..., min_length=1)


class AnalysisResponse(BaseModel):
    id: Optional[str] = None
    media_type: MediaType
    label: PredictionLabel
    confidence: float = Field(..., ge=0, le=100)
    explanation: str
    frames_analyzed: Optional[int] = None
    firebase_url: Optional[str] = None
    heatmap_url: Optional[str] = None
    original_filename: Optional[str] = None
    saved_record: Optional[Dict[str, Any]] = None


class VideoAnalysisResponse(AnalysisResponse):
    media_type: Literal["video"]
    frames_analyzed: int = Field(..., ge=1)
