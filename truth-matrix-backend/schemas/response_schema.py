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
    fake_probability: Optional[float] = Field(default=None, ge=0, le=100)
    authentic_probability: Optional[float] = Field(default=None, ge=0, le=100)
    explanation: str
    frames_analyzed: Optional[int] = None
    firebase_url: Optional[str] = None
    heatmap_url: Optional[str] = None
    xai_overlay_url: Optional[str] = None
    xai_panel_url: Optional[str] = None
    xai_method: Optional[str] = None
    xai_target_class: Optional[str] = None
    xai_predicted_class: Optional[str] = None
    xai_layer: Optional[str] = None
    xai_map_strength: Optional[float] = None
    xai_error: Optional[str] = None
    original_filename: Optional[str] = None
    saved_record: Optional[Dict[str, Any]] = None


class VideoAnalysisResponse(AnalysisResponse):
    media_type: Literal["video"]
    frames_analyzed: int = Field(..., ge=1)
