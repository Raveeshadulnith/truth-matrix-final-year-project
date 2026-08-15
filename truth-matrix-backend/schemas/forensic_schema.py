from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue


JsonObject = Dict[str, JsonValue]


class ForensicContractModel(BaseModel):
    """Base model that rejects accidental, undocumented contract fields."""

    model_config = ConfigDict(extra="forbid")


class OverallForensicStatus(str, Enum):
    """Completion state for the combined forensic collection run."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ExtractorStatus(str, Enum):
    """Availability state for one independent forensic extractor."""

    AVAILABLE = "available"
    NOT_PRESENT = "not_present"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class FindingSeverity(str, Enum):
    """Review priority for a forensic finding, not a manipulation verdict."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class C2paSignatureState(str, Enum):
    """Cryptographic signature result, independent of certificate trust."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class C2paTrustState(str, Enum):
    """Certificate trust result, independent of signature validity."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    NOT_CHECKED = "not_checked"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class C2paValidationState(str, Enum):
    """Asset/manifest validation result, independent of signer trust."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class C2paValidationCategory(str, Enum):
    """SDK validation-result category retained without resource URLs."""

    SUCCESS = "success"
    INFORMATIONAL = "informational"
    FAILURE = "failure"


class C2paOriginState(str, Enum):
    """User-facing conclusion derived from a verified active-manifest action."""

    VERIFIED_AI_GENERATED = "verified_ai_generated"
    DECLARED_AI_GENERATED_UNTRUSTED = "declared_ai_generated_untrusted"
    VERIFIED_AI_EDITED = "verified_ai_edited"
    DECLARED_AI_EDITED_UNTRUSTED = "declared_ai_edited_untrusted"
    VERIFIED_CAMERA_CAPTURE = "verified_camera_capture"
    VERIFIED_SCREEN_CAPTURE = "verified_screen_capture"
    VERIFIED_HUMAN_EDITED = "verified_human_edited"
    VERIFIED_DIGITAL_CREATION = "verified_digital_creation"
    VERIFIED_MIXED_OR_SYNTHETIC = "verified_mixed_or_synthetic"
    NO_ORIGIN_DECLARATION = "no_origin_declaration"
    INVALID_CREDENTIAL = "invalid_credential"
    VERIFICATION_UNAVAILABLE = "verification_unavailable"
    UNKNOWN = "unknown"


class C2paOriginCategory(str, Enum):
    """Controlled origin/workflow category, independent of model inference."""

    AI_GENERATED = "ai_generated"
    AI_EDITED = "ai_edited"
    CAMERA_CAPTURE = "camera_capture"
    SCREEN_CAPTURE = "screen_capture"
    HUMAN_EDITED = "human_edited"
    DIGITAL_CREATION = "digital_creation"
    MIXED_OR_SYNTHETIC = "mixed_or_synthetic"
    UNKNOWN = "unknown"


class C2paBasisStrength(str, Enum):
    """Verification basis supporting a C2PA provenance conclusion."""

    VALID_TRUSTED = "valid_trusted"
    VALID_UNTRUSTED = "valid_untrusted"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"
    NONE = "none"


class SimilarityMatchType(str, Enum):
    """Relationship reported by a user-scoped similarity search."""

    EXACT = "exact"
    NEAR = "near"


class ForensicAssessmentState(str, Enum):
    """Plain-language outcome of deterministic forensic review prioritization."""

    NO_MATERIAL_CONCERNS = "no_material_concerns"
    REVIEW_SIGNALS_PRESENT = "review_signals_present"
    STRONG_CONFLICTS_PRESENT = "strong_conflicts_present"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    COLLECTION_FAILED = "collection_failed"


class ForensicConcernBand(str, Enum):
    """Ordinal review-priority band; never an authenticity probability."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ForensicInsightCategory(str, Enum):
    """Stable user-facing category for a synthesized forensic observation."""

    INTEGRITY = "integrity"
    ORIGIN = "origin"
    TIMELINE = "timeline"
    WORKFLOW = "workflow"
    PROVENANCE = "provenance"
    ENCODING = "encoding"
    SIMILARITY = "similarity"
    AVAILABILITY = "availability"


class ForensicInsightTone(str, Enum):
    """Accessible presentation tone independent of ML classes."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    CAUTION = "caution"
    WARNING = "warning"


class EvidenceStrength(str, Enum):
    """Qualitative strength of one score contribution."""

    LIMITED = "limited"
    MODERATE = "moderate"
    STRONG = "strong"


class ModelForensicAlignmentState(str, Enum):
    """Qualitative relationship between independent model and forensic results."""

    SUPPORTS_MODEL_RESULT = "supports_model_result"
    NO_MATERIAL_EFFECT = "no_material_effect"
    CONFLICTS_WITH_MODEL_RESULT = "conflicts_with_model_result"
    INSUFFICIENT_FOR_COMPARISON = "insufficient_for_comparison"


class SoftwareCategory(str, Enum):
    """Conservative role assigned to an explicitly named workflow tool."""

    CAPTURE_PROCESSING = "capture_processing"
    EDITOR = "editor"
    ENCODER = "encoder"
    AI_GENERATION = "ai_generation"
    SOCIAL_PLATFORM = "social_platform"
    METADATA_TOOL = "metadata_tool"
    UNKNOWN = "unknown"


class MetadataEvidence(ForensicContractModel):
    """Bounded and sanitized metadata from one or more local extractors."""

    status: ExtractorStatus
    source: Optional[str] = None
    source_version: Optional[str] = None
    normalized: JsonObject = Field(default_factory=dict)
    raw: JsonObject = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class SoftwareObservation(ForensicContractModel):
    """Deduplicated software name, role, provenance, and user explanation."""

    name: str = Field(..., min_length=1)
    category: SoftwareCategory
    source_tags: List[str] = Field(default_factory=list, max_length=16)
    user_description: str = Field(..., min_length=1)


class CreationInfo(ForensicContractModel):
    """Conservatively normalized creation details with precise GPS omitted."""

    software: List[str] = Field(default_factory=list)
    software_observations: List[SoftwareObservation] = Field(
        default_factory=list, max_length=16
    )
    device_make: Optional[str] = None
    device_model: Optional[str] = None
    creator: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    digitized_at: Optional[str] = None
    timezone_present: bool = False
    location_present: bool = False
    source_tags: Dict[str, List[str]] = Field(default_factory=dict)


class ForensicFinding(ForensicContractModel):
    """A deterministic review signal with evidence and stated limitations."""

    code: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    evidence: JsonObject = Field(default_factory=dict)
    severity: FindingSeverity
    method: Optional[str] = None
    method_version: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)


class C2paAction(ForensicContractModel):
    """Sanitized action summary from an active C2PA manifest."""

    action: str = Field(..., min_length=1)
    digital_source_type: Optional[str] = None
    software_agent: Optional[str] = None
    description: Optional[str] = None
    parameters: JsonObject = Field(default_factory=dict)


class C2paProvenanceConclusion(ForensicContractModel):
    """Bounded explanation of active-manifest origin declarations."""

    origin_state: C2paOriginState
    origin_category: C2paOriginCategory
    basis_strength: C2paBasisStrength
    provider: Optional[str] = None
    claim_generator: Optional[str] = None
    signer: Optional[str] = None
    source_action: Optional[str] = None
    digital_source_type: Optional[str] = None
    headline: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    technical_references: List[str] = Field(default_factory=list, max_length=16)
    limitations: List[str] = Field(default_factory=list, max_length=16)
    classification_method: str = Field(..., min_length=1)
    classification_version: str = Field(..., min_length=1)


class C2paValidationStatus(ForensicContractModel):
    """Sanitized C2PA validation code and bounded human-readable summary."""

    code: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    category: C2paValidationCategory


class C2paEvidence(ForensicContractModel):
    """C2PA presence, signature validity, and trust as separate facts."""

    status: ExtractorStatus
    manifest_present: bool
    active_manifest: Optional[str] = None
    validation_state: C2paValidationState = C2paValidationState.UNKNOWN
    signature_state: C2paSignatureState
    trust_state: C2paTrustState
    signer: Optional[str] = None
    issuer: Optional[str] = None
    claim_generator: Optional[str] = None
    claim_generator_version: Optional[str] = None
    assertion_labels: List[str] = Field(default_factory=list)
    actions: List[C2paAction] = Field(default_factory=list)
    ingredient_count: int = Field(default=0, ge=0)
    validation_statuses: List[C2paValidationStatus] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    provenance: Optional[C2paProvenanceConclusion] = None
    remote_references_present: bool = False
    remote_fetch_performed: bool = False
    raw_manifest: Optional[JsonObject] = None
    warnings: List[str] = Field(default_factory=list)


class FingerprintComponent(ForensicContractModel):
    """One bounded component in an ordered media fingerprint."""

    value: str = Field(..., min_length=1)
    index: int = Field(..., ge=0)
    timestamp_seconds: Optional[float] = Field(default=None, ge=0)


class PerceptualFingerprint(ForensicContractModel):
    """Media-specific similarity fingerprint; never an integrity identifier."""

    status: ExtractorStatus
    algorithm: Optional[str] = None
    algorithm_version: Optional[str] = None
    value: Optional[str] = None
    hash_size: Optional[int] = Field(default=None, ge=1)
    components: List[FingerprintComponent] = Field(default_factory=list)
    duration_seconds: Optional[float] = Field(default=None, ge=0)
    warnings: List[str] = Field(default_factory=list)


class SimilarityMatch(ForensicContractModel):
    """A bounded exact or near match from the authenticated user's history."""

    analysis_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    created_at: str = Field(..., min_length=1)
    match_type: SimilarityMatchType
    similarity_score: float = Field(..., ge=0, le=1)
    distance: Optional[float] = Field(default=None, ge=0)
    details: JsonObject = Field(default_factory=dict)
    algorithm: str = Field(..., min_length=1)
    algorithm_version: Optional[str] = None


class ForensicInsight(ForensicContractModel):
    """Bounded plain-language observation derived from technical evidence."""

    code: str = Field(..., min_length=1)
    category: ForensicInsightCategory
    tone: ForensicInsightTone
    title: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    technical_references: List[str] = Field(default_factory=list, max_length=16)


class ForensicScoreContribution(ForensicContractModel):
    """Explainable non-zero contribution to an ordinal review score."""

    finding_code: str = Field(..., min_length=1)
    points: int = Field(..., ge=1, le=100)
    reason: str = Field(..., min_length=1)
    evidence_strength: EvidenceStrength
    limitations: List[str] = Field(default_factory=list, max_length=16)


class ModelForensicAlignment(ForensicContractModel):
    """Explainable, non-mathematical comparison of model and file evidence."""

    alignment_state: ModelForensicAlignmentState
    headline: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    model_label: Literal["Authentic", "Suspected Deepfake"]
    forensic_assessment_state: ForensicAssessmentState
    limitations: List[str] = Field(default_factory=list, max_length=16)
    alignment_method: str = Field(..., min_length=1)
    alignment_version: str = Field(..., min_length=1)


class ForensicAssessment(ForensicContractModel):
    """Versioned synthesis of evidence for review, not fake probability."""

    assessment_state: ForensicAssessmentState
    review_concern_score: int = Field(..., ge=0, le=100)
    concern_band: ForensicConcernBand
    evidence_coverage_score: int = Field(..., ge=0, le=100)
    headline: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    key_insights: List[ForensicInsight] = Field(default_factory=list, max_length=5)
    score_contributions: List[ForensicScoreContribution] = Field(
        default_factory=list, max_length=32
    )
    limitations: List[str] = Field(default_factory=list, max_length=16)
    scoring_method: str = Field(..., min_length=1)
    scoring_version: str = Field(..., min_length=1)
    model_alignment: Optional[ModelForensicAlignment] = None


class ForensicEvidence(ForensicContractModel):
    """Versioned evidence aggregate returned alongside an ML prediction."""

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.2"
    status: OverallForensicStatus
    file_identity_status: ExtractorStatus
    sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    file_size_bytes: Optional[int] = Field(default=None, ge=0)
    detected_mime_type: Optional[str] = None
    metadata: MetadataEvidence
    creation_info: CreationInfo
    metadata_inconsistency_status: ExtractorStatus
    metadata_inconsistencies: List[ForensicFinding] = Field(default_factory=list)
    compression_status: ExtractorStatus
    compression_indicators: List[ForensicFinding] = Field(default_factory=list)
    c2pa: C2paEvidence
    perceptual_fingerprint: PerceptualFingerprint
    similarity_status: ExtractorStatus
    similarity_matches: List[SimilarityMatch] = Field(default_factory=list)
    assessment: Optional[ForensicAssessment] = None
    warnings: List[str] = Field(default_factory=list)
    processing_time_ms: int = Field(..., ge=0)
