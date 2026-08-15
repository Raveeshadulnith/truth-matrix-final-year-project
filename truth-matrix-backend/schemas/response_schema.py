from typing import Any, Dict, Literal, Optional

import math

from pydantic import BaseModel, Field, model_validator

from schemas.forensic_schema import ForensicEvidence, ModelForensicAlignment


PredictionLabel = Literal["Authentic", "Suspected Deepfake"]
MediaType = Literal["image", "video", "audio"]


class ImageUrlRequest(BaseModel):
    image_url: str = Field(..., min_length=1)


class PreciseLocationResponse(BaseModel):
    """Owner-only, non-cacheable precise embedded location response."""

    status: Literal["available", "not_present", "invalid", "unavailable", "forbidden"]
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    altitude_meters: Optional[float] = None
    source: Optional[str] = Field(default=None, max_length=96)
    accuracy_meters: Optional[float] = Field(default=None, ge=0)


class ImageModelReadinessResponse(BaseModel):
    status: Literal["ready"]
    model_version: str = Field(..., min_length=1, max_length=128)
    device: Literal["cpu", "cuda"]
    loaded: Literal[True]


class AudioModelReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    model_identifier: Literal["deepfake-audio-detection-v2"]
    model_version: str = Field(..., min_length=1, max_length=128)
    device: Optional[Literal["cpu", "cuda"]] = None
    error_category: Optional[
        Literal[
            "configuration_invalid",
            "model_files_invalid",
            "revision_invalid",
            "decoder_unavailable",
            "model_contract_invalid",
            "feature_extractor_invalid",
            "device_unavailable",
            "model_load_failed",
            "warmup_failed",
            "unexpected",
        ]
    ] = None


class AnalysisResponse(BaseModel):
    id: Optional[str] = None
    media_type: MediaType
    label: PredictionLabel
    confidence: float = Field(..., ge=0, le=100)
    fake_probability: Optional[float] = Field(default=None, ge=0, le=100)
    authentic_probability: Optional[float] = Field(default=None, ge=0, le=100)
    explanation: str
    frames_analyzed: Optional[int] = None
    local_url: Optional[str] = None
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
    model_version: Optional[str] = Field(default=None, max_length=128)
    original_filename: Optional[str] = None
    forensic_evidence: Optional[ForensicEvidence] = None
    model_forensic_alignment: Optional[ModelForensicAlignment] = None
    saved_record: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_probability_pair(self) -> "AnalysisResponse":
        """Reject non-finite probabilities and inconsistent two-class totals."""
        probabilities = (self.fake_probability, self.authentic_probability)
        for probability in probabilities:
            if probability is not None and not math.isfinite(probability):
                raise ValueError("model probabilities must be finite")
        if all(probability is not None for probability in probabilities):
            total = sum(
                probability
                for probability in probabilities
                if probability is not None
            )
            if not math.isclose(total, 100.0, abs_tol=0.1):
                raise ValueError(
                    "model probabilities must sum to approximately 100"
                )
        return self


class VideoAnalysisResponse(AnalysisResponse):
    media_type: Literal["video"]
    frames_analyzed: int = Field(..., ge=1)
    video_metadata: Dict[str, Any]
