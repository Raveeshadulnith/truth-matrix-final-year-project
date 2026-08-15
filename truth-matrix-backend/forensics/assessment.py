from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from forensics.c2pa_provenance import classify_c2pa_provenance
from schemas.forensic_schema import (
    EvidenceStrength,
    C2paProvenanceConclusion,
    ExtractorStatus,
    ForensicAssessment,
    ForensicConcernBand,
    ForensicEvidence,
    ForensicFinding,
    ForensicInsight,
    ForensicInsightCategory,
    ForensicInsightTone,
    ForensicScoreContribution,
    ModelForensicAlignment,
    OverallForensicStatus,
    SoftwareCategory,
)


SCORING_METHOD = "deterministic-code-specific-review-prioritization"
SCORING_VERSION = "1.0"
ALIGNMENT_METHOD = "qualitative-independent-model-forensic-comparison"
ALIGNMENT_VERSION = "1.0"
DEFAULT_MIN_COVERAGE_SCORE = 40
DEFAULT_MODERATE_THRESHOLD = 20
DEFAULT_HIGH_THRESHOLD = 50
DEFAULT_MAX_INSIGHTS = 5

_SUCCESS_STATUSES = {
    ExtractorStatus.AVAILABLE,
    ExtractorStatus.NOT_PRESENT,
    ExtractorStatus.UNSUPPORTED,
}
_COVERAGE_WEIGHTS = {
    "identity": 25,
    "metadata": 20,
    "consistency": 10,
    "compression": 15,
    "c2pa": 15,
    "fingerprint": 15,
}
_GROUP_CAPS = {
    "c2pa": 50,
    "file_type": 25,
    "timeline": 25,
    "metadata_structure": 25,
    "duration": 12,
    "container": 30,
    "image_heuristic": 5,
}
_STANDARD_LIMITATIONS = [
    "The review concern score is ordinal prioritization, not the probability that media is fake.",
    "A low score or absence of detected conflicts does not prove authenticity.",
    "Metadata can be missing, stripped, stale, copied, or rewritten during ordinary workflows.",
    "Content Credentials describe provenance; they do not prove that a depicted claim is true.",
]


@dataclass(frozen=True)
class ForensicAssessmentConfig:
    """Validated thresholds controlling presentation bands and sufficiency."""

    minimum_coverage_score: int
    moderate_threshold: int
    high_threshold: int
    maximum_insights: int
    scoring_version: str = SCORING_VERSION


@dataclass(frozen=True)
class _ScoringRule:
    points: int
    group: str
    reason: str
    category: ForensicInsightCategory


@dataclass(frozen=True)
class _Candidate:
    code: str
    points: int
    group: str
    reason: str
    category: ForensicInsightCategory
    title: str
    limitations: Sequence[str]


_FINDING_RULES: Dict[str, _ScoringRule] = {
    "file_type.extension_mismatch": _ScoringRule(
        8,
        "file_type",
        "The filename extension conflicts with the media type detected from the file bytes.",
        ForensicInsightCategory.INTEGRITY,
    ),
    "file_type.declared_mime_mismatch": _ScoringRule(
        5,
        "file_type",
        "The client-declared media type conflicts with the type detected from the file bytes.",
        ForensicInsightCategory.INTEGRITY,
    ),
    "file_type.container_mismatch": _ScoringRule(
        20,
        "file_type",
        "Recognized container metadata conflicts with the byte-detected media type.",
        ForensicInsightCategory.INTEGRITY,
    ),
    "metadata.timestamp_unparseable": _ScoringRule(
        5,
        "timeline",
        "An embedded date is impossible or cannot be parsed conservatively.",
        ForensicInsightCategory.TIMELINE,
    ),
    "metadata.timestamp_order_conflict": _ScoringRule(
        20,
        "timeline",
        "Comparable embedded dates place modification before creation beyond the allowed tolerance.",
        ForensicInsightCategory.TIMELINE,
    ),
    "metadata.timestamp_group_conflict": _ScoringRule(
        12,
        "timeline",
        "Different embedded metadata groups report materially conflicting dates.",
        ForensicInsightCategory.TIMELINE,
    ),
    "metadata.gps_out_of_range": _ScoringRule(
        15,
        "metadata_structure",
        "Embedded location data contains a coordinate outside its legal range.",
        ForensicInsightCategory.ORIGIN,
    ),
    "metadata.dimension_conflict": _ScoringRule(
        15,
        "metadata_structure",
        "Independent metadata locations report incompatible media dimensions.",
        ForensicInsightCategory.INTEGRITY,
    ),
    "metadata.orientation_conflict": _ScoringRule(
        5,
        "metadata_structure",
        "Embedded metadata locations report conflicting orientations.",
        ForensicInsightCategory.INTEGRITY,
    ),
    "metadata.device_conflict": _ScoringRule(
        10,
        "metadata_structure",
        "Embedded metadata reports mutually conflicting capture-device information.",
        ForensicInsightCategory.ORIGIN,
    ),
    "metadata.duration_conflict": _ScoringRule(
        10,
        "duration",
        "Container and stream metadata report materially different durations.",
        ForensicInsightCategory.ENCODING,
    ),
    "compression.duration_disagreement": _ScoringRule(
        8,
        "duration",
        "Container and stream duration measurements disagree beyond the configured tolerance.",
        ForensicInsightCategory.ENCODING,
    ),
    "compression.container_codec_mismatch": _ScoringRule(
        20,
        "container",
        "The reported codec is unusual or incompatible with the detected container.",
        ForensicInsightCategory.ENCODING,
    ),
    "compression.expected_stream_missing": _ScoringRule(
        25,
        "container",
        "An expected audio or video stream is missing from the media container.",
        ForensicInsightCategory.ENCODING,
    ),
    "compression.jpeg_block_discontinuity": _ScoringRule(
        3,
        "image_heuristic",
        "The JPEG block-boundary measurement exceeded its conservative review threshold.",
        ForensicInsightCategory.ENCODING,
    ),
}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def load_assessment_config() -> ForensicAssessmentConfig:
    """Load and validate forensic assessment thresholds from the environment."""
    moderate = _env_int(
        "FORENSIC_ASSESSMENT_MODERATE_THRESHOLD",
        DEFAULT_MODERATE_THRESHOLD,
        1,
        98,
    )
    high = _env_int(
        "FORENSIC_ASSESSMENT_HIGH_THRESHOLD",
        DEFAULT_HIGH_THRESHOLD,
        2,
        99,
    )
    if moderate >= high:
        raise ValueError(
            "FORENSIC_ASSESSMENT_MODERATE_THRESHOLD must be lower than "
            "FORENSIC_ASSESSMENT_HIGH_THRESHOLD"
        )
    return ForensicAssessmentConfig(
        minimum_coverage_score=_env_int(
            "FORENSIC_ASSESSMENT_MIN_COVERAGE_SCORE",
            DEFAULT_MIN_COVERAGE_SCORE,
            0,
            100,
        ),
        moderate_threshold=moderate,
        high_threshold=high,
        maximum_insights=_env_int(
            "FORENSIC_ASSESSMENT_MAX_INSIGHTS",
            DEFAULT_MAX_INSIGHTS,
            1,
            5,
        ),
    )


def _coverage_score(evidence: ForensicEvidence) -> int:
    statuses = {
        "identity": evidence.file_identity_status,
        "metadata": evidence.metadata.status,
        "consistency": evidence.metadata_inconsistency_status,
        "compression": evidence.compression_status,
        "c2pa": evidence.c2pa.status,
        "fingerprint": evidence.perceptual_fingerprint.status,
    }
    return sum(
        _COVERAGE_WEIGHTS[name]
        for name, status in statuses.items()
        if status in _SUCCESS_STATUSES
    )


def _finding_candidates(findings: Iterable[ForensicFinding]) -> List[_Candidate]:
    by_code: Dict[str, _Candidate] = {}
    for finding in findings:
        rule = _FINDING_RULES.get(finding.code)
        if rule is None:
            continue
        points = rule.points
        if (
            finding.code == "compression.jpeg_block_discontinuity"
            and finding.severity.value == "info"
        ):
            points = 0
        if points <= 0:
            continue
        candidate = _Candidate(
            code=finding.code,
            points=points,
            group=rule.group,
            reason=rule.reason,
            category=rule.category,
            title=finding.title,
            limitations=tuple(finding.limitations),
        )
        by_code.setdefault(finding.code, candidate)
    return list(by_code.values())


def _c2pa_candidates(evidence: ForensicEvidence) -> List[_Candidate]:
    candidates: List[_Candidate] = []
    if evidence.c2pa.signature_state.value == "invalid":
        candidates.append(
            _Candidate(
                code="c2pa.signature_invalid",
                points=50,
                group="c2pa",
                reason="The Content Credentials signature failed cryptographic validation.",
                category=ForensicInsightCategory.PROVENANCE,
                title="Content Credentials signature is invalid",
                limitations=(
                    "A signature failure can result from tampering, corruption, or an invalid manifest; it does not identify who changed the asset.",
                ),
            )
        )
    if evidence.c2pa.validation_state.value == "invalid":
        candidates.append(
            _Candidate(
                code="c2pa.asset_validation_invalid",
                points=50,
                group="c2pa",
                reason="The signed asset or active manifest failed C2PA validation.",
                category=ForensicInsightCategory.PROVENANCE,
                title="Content Credentials asset validation failed",
                limitations=(
                    "Validation failure is a provenance integrity signal, not proof that the depicted content is false.",
                ),
            )
        )
    return candidates


def _strength(points: int) -> EvidenceStrength:
    if points >= 30:
        return EvidenceStrength.STRONG
    if points >= 10:
        return EvidenceStrength.MODERATE
    return EvidenceStrength.LIMITED


def _bounded_contributions(candidates: Iterable[_Candidate]) -> List[ForensicScoreContribution]:
    group_totals: Dict[str, int] = {}
    total = 0
    contributions: List[ForensicScoreContribution] = []
    for candidate in sorted(candidates, key=lambda item: (-item.points, item.code)):
        group_remaining = _GROUP_CAPS[candidate.group] - group_totals.get(candidate.group, 0)
        total_remaining = 100 - total
        points = min(candidate.points, group_remaining, total_remaining)
        if points <= 0:
            continue
        contributions.append(
            ForensicScoreContribution(
                finding_code=candidate.code,
                points=points,
                reason=candidate.reason,
                evidence_strength=_strength(points),
                limitations=list(candidate.limitations)[:16],
            )
        )
        group_totals[candidate.group] = group_totals.get(candidate.group, 0) + points
        total += points
        if total >= 100:
            break
    return contributions


def _concern_band(score: int, config: ForensicAssessmentConfig) -> ForensicConcernBand:
    if score >= config.high_threshold:
        return ForensicConcernBand.HIGH
    if score >= config.moderate_threshold:
        return ForensicConcernBand.MODERATE
    return ForensicConcernBand.LOW


def _state_and_copy(
    evidence: ForensicEvidence,
    score: int,
    coverage: int,
    config: ForensicAssessmentConfig,
) -> tuple[str, str, str]:
    if evidence.status == OverallForensicStatus.ERROR:
        return (
            "collection_failed",
            "Forensic assessment could not be completed",
            "The forensic collection process failed, so no reliable file-level assessment is available.",
        )
    if score >= config.high_threshold:
        return (
            "strong_conflicts_present",
            "Strong conflicts were found in the file evidence",
            "The collected evidence contains one or more strong integrity or consistency signals that warrant human review.",
        )
    if score > 0:
        return (
            "review_signals_present",
            "Some file details deserve review",
            "The collected evidence contains limited or moderate file-level signals with possible benign explanations.",
        )
    if coverage < config.minimum_coverage_score:
        return (
            "insufficient_evidence",
            "Not enough forensic evidence was available",
            "Too little applicable file-level evidence was collected for a useful forensic assessment.",
        )
    return (
        "no_material_concerns",
        "No significant file-level concerns found",
        "No scored integrity or consistency conflicts were identified in the evidence that was successfully collected.",
    )


def _append_insight(
    insights: List[ForensicInsight],
    insight: ForensicInsight,
    maximum: int,
) -> None:
    if len(insights) >= maximum or any(item.code == insight.code for item in insights):
        return
    insights.append(insight)


def _finding_priority(candidate: _Candidate, points: int) -> tuple[int, int, str]:
    """Order primary concerns by product meaning rather than extractor order."""
    if candidate.code.startswith("c2pa."):
        priority = 0
    elif candidate.group in {
        "file_type",
        "timeline",
        "metadata_structure",
        "duration",
        "container",
    }:
        priority = 1
    else:
        priority = 6
    return priority, -points, candidate.code


def _workflow_insights(evidence: ForensicEvidence) -> List[ForensicInsight]:
    """Translate deduplicated software roles into neutral workflow conclusions."""
    output: List[ForensicInsight] = []
    for observation in evidence.creation_info.software_observations:
        if observation.category == SoftwareCategory.CAPTURE_PROCESSING:
            message = (
                f"{observation.name} is normal camera-processing software and is "
                "not evidence of manual editing."
            )
            tone = ForensicInsightTone.POSITIVE
            title = "Camera-processing software was identified"
        elif observation.category == SoftwareCategory.EDITOR:
            message = (
                f"The metadata names {observation.name}, software commonly used for "
                "editing or post-processing. This can reflect an ordinary workflow "
                "and does not prove deceptive manipulation."
            )
            tone = ForensicInsightTone.NEUTRAL
            title = "Post-processing software was named"
        elif observation.category == SoftwareCategory.ENCODER:
            message = (
                f"The metadata names {observation.name} as encoding or export software. "
                "Encoding is common and is not the same as evidence of editing."
            )
            tone = ForensicInsightTone.NEUTRAL
            title = "Encoding software was identified"
        elif observation.category == SoftwareCategory.AI_GENERATION:
            message = (
                f"The metadata explicitly names {observation.name}, a generative-media "
                "system. Metadata can be stale or copied, so this warrants review but "
                "does not prove how the media was created."
            )
            tone = ForensicInsightTone.CAUTION
            title = "A named generative-media system appears in metadata"
        elif observation.category == SoftwareCategory.SOCIAL_PLATFORM:
            message = (
                f"The metadata names {observation.name}, which may have recompressed or "
                "rewritten the file during sharing."
            )
            tone = ForensicInsightTone.NEUTRAL
            title = "A sharing platform appears in the workflow"
        elif observation.category == SoftwareCategory.METADATA_TOOL:
            message = (
                f"The metadata names {observation.name}, a metadata-management tool. "
                "This does not establish that the media content changed."
            )
            tone = ForensicInsightTone.NEUTRAL
            title = "A metadata tool appears in the workflow"
        else:
            message = (
                f"The file names {observation.name}, but its role cannot be classified "
                "safely from metadata alone."
            )
            tone = ForensicInsightTone.NEUTRAL
            title = "Software metadata was preserved"
        output.append(
            ForensicInsight(
                code=f"workflow.software.{observation.category.value}",
                category=ForensicInsightCategory.WORKFLOW,
                tone=tone,
                title=title,
                user_message=message,
                technical_references=observation.source_tags[:16],
            )
        )
    return output


def _key_insights(
    evidence: ForensicEvidence,
    candidates: Sequence[_Candidate],
    contributions: Sequence[ForensicScoreContribution],
    maximum: int,
) -> List[ForensicInsight]:
    candidate_by_code = {candidate.code: candidate for candidate in candidates}
    insights: List[ForensicInsight] = []
    provenance = evidence.c2pa.provenance or classify_c2pa_provenance(evidence.c2pa)
    verified_provenance = provenance.origin_state.value in {
        "verified_ai_generated",
        "verified_ai_edited",
    }
    contribution_limit = max(0, maximum - 1) if verified_provenance else maximum

    ordered_contributions = sorted(
        contributions,
        key=lambda contribution: _finding_priority(
            candidate_by_code[contribution.finding_code], contribution.points
        ),
    )
    for contribution in ordered_contributions:
        if len(insights) >= contribution_limit:
            break
        candidate = candidate_by_code[contribution.finding_code]
        if candidate.group == "image_heuristic":
            continue
        _append_insight(
            insights,
            ForensicInsight(
                code=candidate.code,
                category=candidate.category,
                tone=(
                    ForensicInsightTone.WARNING
                    if contribution.evidence_strength == EvidenceStrength.STRONG
                    else ForensicInsightTone.CAUTION
                ),
                title=candidate.title,
                user_message=contribution.reason,
                technical_references=[candidate.code],
            ),
            maximum,
        )

    if verified_provenance:
        _append_insight(
            insights,
            ForensicInsight(
                code=f"c2pa.provenance.{provenance.origin_state.value}",
                category="provenance",
                tone="positive",
                title=provenance.headline,
                user_message=provenance.user_message,
                technical_references=provenance.technical_references,
            ),
            maximum,
        )

    if evidence.file_identity_status == ExtractorStatus.AVAILABLE:
        media_name = evidence.detected_mime_type or "a supported media type"
        type_conflict_codes = {
            "file_type.extension_mismatch",
            "file_type.declared_mime_mismatch",
            "file_type.container_mismatch",
        }
        consistent = not any(
            finding.code in type_conflict_codes
            for finding in evidence.metadata_inconsistencies
        )
        friendly_type = {
            "image/jpeg": "a JPEG image",
            "image/png": "a PNG image",
            "image/webp": "a WebP image",
            "video/mp4": "an MP4 video",
            "video/quicktime": "a QuickTime video",
            "audio/wav": "a WAV audio file",
            "audio/mpeg": "an MP3 audio file",
        }.get(media_name, media_name)
        _append_insight(
            insights,
            ForensicInsight(
                code="integrity.file_identity_available",
                category="integrity",
                tone="positive",
                title=(
                    "File type is internally consistent"
                    if consistent
                    else "File identity was established"
                ),
                user_message=(
                    f"The file identifies itself consistently as {friendly_type}."
                    if consistent
                    else f"The file bytes were hashed and identified as {media_name}."
                ),
                technical_references=["sha256", "detected_mime_type"],
            ),
            maximum,
        )

    device = " ".join(
        value
        for value in (evidence.creation_info.device_make, evidence.creation_info.device_model)
        if value
    ).strip()
    if device:
        _append_insight(
            insights,
            ForensicInsight(
                code="origin.embedded_device",
                category="origin",
                tone="neutral",
                title="Embedded device information is available",
                user_message=f"Camera metadata names a {device}.",
                technical_references=[
                    *evidence.creation_info.source_tags.get("device_make", []),
                    *evidence.creation_info.source_tags.get("device_model", []),
                ][:16],
            ),
            maximum,
        )

    if not evidence.creation_info.created_at and evidence.metadata.status in {
        ExtractorStatus.AVAILABLE,
        ExtractorStatus.NOT_PRESENT,
    }:
        _append_insight(
            insights,
            ForensicInsight(
                code="timeline.capture_time_not_present",
                category="timeline",
                tone="neutral",
                title="Embedded capture time was not available",
                user_message=(
                    "The embedded capture time was not available. Missing dates are "
                    "common and do not suggest that the media is fake."
                ),
                technical_references=["creation_info.created_at"],
            ),
            maximum,
        )

    for workflow_insight in _workflow_insights(evidence):
        _append_insight(insights, workflow_insight, maximum)

    if evidence.creation_info.location_present:
        _append_insight(
            insights,
            ForensicInsight(
                code="origin.location_metadata_present",
                category="origin",
                tone="neutral",
                title="Location metadata was present",
                user_message=(
                    "Location metadata was embedded, but exact coordinates are hidden "
                    "to protect privacy."
                ),
                technical_references=evidence.creation_info.source_tags.get(
                    "location_present", []
                )[:16],
            ),
            maximum,
        )

    if provenance and provenance.origin_state.value in {
        "verified_ai_generated",
        "verified_ai_edited",
    }:
        pass
    elif (
        evidence.c2pa.manifest_present
        and evidence.c2pa.signature_state.value == "valid"
        and evidence.c2pa.trust_state.value == "trusted"
    ):
        _append_insight(
            insights,
            ForensicInsight(
                code="c2pa.valid_trusted",
                category="provenance",
                tone="positive",
                title="Content Credentials signature and signer trust verified",
                user_message="The local verifier validated the signature and anchored the signer in the configured trust store; this does not prove the depicted claim is true.",
                technical_references=["c2pa.signature_state", "c2pa.trust_state"],
            ),
            maximum,
        )
    elif (
        evidence.c2pa.manifest_present
        and evidence.c2pa.signature_state.value == "valid"
        and evidence.c2pa.trust_state.value == "untrusted"
    ):
        _append_insight(
            insights,
            ForensicInsight(
                code="c2pa.valid_untrusted",
                category="provenance",
                tone="caution",
                title="Signature valid; signer trust not established",
                user_message="The signature is cryptographically valid, but the signer is not anchored in the configured trust store.",
                technical_references=["c2pa.signature_state", "c2pa.trust_state"],
            ),
            maximum,
        )
    elif evidence.c2pa.status == ExtractorStatus.NOT_PRESENT:
        _append_insight(
            insights,
            ForensicInsight(
                code="c2pa.not_present",
                category="provenance",
                tone="neutral",
                title="No Content Credentials were attached",
                user_message="Most media does not contain Content Credentials, so their absence does not increase review concern.",
                technical_references=["c2pa.status"],
            ),
            maximum,
        )

    if evidence.similarity_matches:
        exact = sum(match.match_type.value == "exact" for match in evidence.similarity_matches)
        near = len(evidence.similarity_matches) - exact
        _append_insight(
            insights,
            ForensicInsight(
                code="similarity.history_matches",
                category="similarity",
                tone="neutral",
                title="Related media was found in your history",
                user_message=(
                    f"The bounded user-scoped search found {exact} exact and {near} near match(es); matches do not prove authorship or manipulation."
                ),
                technical_references=["similarity_matches"],
            ),
            maximum,
        )

    if evidence.metadata.status in {ExtractorStatus.UNAVAILABLE, ExtractorStatus.ERROR}:
        _append_insight(
            insights,
            ForensicInsight(
                code="availability.metadata_unavailable",
                category="availability",
                tone="neutral",
                title="Some embedded metadata could not be examined",
                user_message="Unavailable metadata reduces evidence coverage but does not increase review concern.",
                technical_references=["metadata.status"],
            ),
            maximum,
        )
    elif evidence.status in {
        OverallForensicStatus.PARTIAL,
        OverallForensicStatus.UNAVAILABLE,
        OverallForensicStatus.ERROR,
    }:
        _append_insight(
            insights,
            ForensicInsight(
                code="availability.collection_limited",
                category="availability",
                tone="neutral",
                title="Some forensic sources were unavailable",
                user_message=(
                    "Some applicable file evidence could not be collected. This limits "
                    "the conclusion but does not itself suggest manipulation."
                ),
                technical_references=["status", "warnings"],
            ),
            maximum,
        )
    return insights


def align_model_and_forensics(
    model_label: str,
    assessment: ForensicAssessment,
    provenance: Optional[C2paProvenanceConclusion] = None,
) -> ModelForensicAlignment:
    """Compare independent results qualitatively without changing either result."""
    if model_label not in {"Authentic", "Suspected Deepfake"}:
        raise ValueError("model_label must be Authentic or Suspected Deepfake")

    forensic_state = assessment.assessment_state
    insufficient = forensic_state in {
        "insufficient_evidence",
        "collection_failed",
    }
    strong_conflicts = forensic_state == "strong_conflicts_present"
    review_signals = forensic_state == "review_signals_present"

    provenance_state = provenance.origin_state.value if provenance else None
    verified_ai_generated = provenance_state == "verified_ai_generated"
    verified_ai_edited = provenance_state == "verified_ai_edited"

    if model_label == "Authentic" and verified_ai_generated:
        state = "conflicts_with_model_result"
        headline = "Model and verified provenance point in different directions"
        summary = (
            "The model suggests authentic content, but trusted Content Credentials "
            "declare an AI-generated origin. The independent results conflict and "
            "deserve review."
        )
    elif model_label == "Suspected Deepfake" and verified_ai_generated:
        state = "supports_model_result"
        headline = "Model and verified provenance both warrant review"
        summary = (
            "The model detected synthetic-media characteristics, and trusted Content "
            "Credentials independently declare an AI-generated origin. These separate "
            "signals were not mathematically combined."
        )
    elif verified_ai_edited:
        state = (
            "supports_model_result"
            if model_label == "Suspected Deepfake"
            else "no_material_effect"
        )
        headline = "Verified provenance declares AI-assisted editing"
        summary = (
            "Trusted Content Credentials declare that Generative AI was used for "
            "editing. This does not establish that the entire media item was generated "
            "by AI and does not change the model result."
        )
    elif insufficient:
        state = "insufficient_for_comparison"
        headline = "Not enough file evidence for comparison"
        summary = (
            "The model result remains available, but too little forensic evidence "
            "was collected for a meaningful independent comparison."
        )
    elif model_label == "Authentic" and strong_conflicts:
        state = "conflicts_with_model_result"
        headline = "Model and file evidence point in different directions"
        summary = (
            "The model suggests authentic content, but the file evidence contains "
            "strong conflicts that deserve review."
        )
    elif model_label == "Suspected Deepfake" and (strong_conflicts or review_signals):
        state = "supports_model_result"
        headline = "Two separate sources warrant review"
        summary = (
            "The model detected deepfake characteristics, and separate file-level "
            "evidence also contains review signals. These results were not "
            "mathematically combined."
        )
    elif model_label == "Suspected Deepfake":
        state = "no_material_effect"
        headline = "File evidence did not independently confirm the model concern"
        summary = (
            "The model detected deepfake characteristics. File metadata did not "
            "provide independent confirmation."
        )
    elif review_signals:
        state = "conflicts_with_model_result"
        headline = "Some file details differ from the model result"
        summary = (
            "The model suggests authentic content, while separate file-level evidence "
            "contains limited or moderate review signals. Benign explanations may exist."
        )
    else:
        state = "supports_model_result"
        headline = "File evidence is consistent with the model result"
        summary = (
            "The model suggests authentic content, and the collected file evidence "
            "contained no material conflicts. This does not prove authenticity."
        )

    return ModelForensicAlignment(
        alignment_state=state,
        headline=headline,
        summary=summary,
        model_label=model_label,
        forensic_assessment_state=forensic_state,
        limitations=[
            "The model and forensic evidence are independent and their percentages are not combined.",
            "Agreement does not prove authenticity, and disagreement requires human review.",
        ],
        alignment_method=ALIGNMENT_METHOD,
        alignment_version=ALIGNMENT_VERSION,
    )


def attach_model_forensic_alignment(
    evidence: ForensicEvidence,
    model_label: str,
) -> tuple[ForensicEvidence, ModelForensicAlignment]:
    """Attach alignment to the stored assessment and return both representations."""
    assessed = evidence if evidence.assessment is not None else attach_forensic_assessment(evidence)
    assert assessed.assessment is not None
    provenance = assessed.c2pa.provenance or classify_c2pa_provenance(assessed.c2pa)
    alignment = align_model_and_forensics(model_label, assessed.assessment, provenance)
    assessment = assessed.assessment.model_copy(update={"model_alignment": alignment})
    return assessed.model_copy(update={"assessment": assessment}), alignment


def assess_forensic_evidence(
    evidence: ForensicEvidence,
    *,
    config: Optional[ForensicAssessmentConfig] = None,
) -> ForensicAssessment:
    """Return a deterministic review assessment without mutating evidence or ML output."""
    settings = config or load_assessment_config()
    findings = [
        *evidence.metadata_inconsistencies,
        *evidence.compression_indicators,
    ]
    candidates = [*_finding_candidates(findings), *_c2pa_candidates(evidence)]
    contributions = _bounded_contributions(candidates)
    score = sum(item.points for item in contributions)
    coverage = _coverage_score(evidence)
    state, headline, summary = _state_and_copy(
        evidence, score, coverage, settings
    )
    return ForensicAssessment(
        assessment_state=state,
        review_concern_score=score,
        concern_band=_concern_band(score, settings),
        evidence_coverage_score=coverage,
        headline=headline,
        summary=(
            f"{summary} The {score}/100 review concern score is not the probability "
            "that the media is fake."
        ),
        key_insights=_key_insights(
            evidence,
            candidates,
            contributions,
            min(settings.maximum_insights, 5),
        ),
        score_contributions=contributions,
        limitations=_STANDARD_LIMITATIONS,
        scoring_method=SCORING_METHOD,
        scoring_version=settings.scoring_version,
    )


def attach_forensic_assessment(evidence: ForensicEvidence) -> ForensicEvidence:
    """Attach the current assessment while isolating synthesis configuration errors."""
    try:
        assessment = assess_forensic_evidence(evidence)
    except Exception:
        assessment = ForensicAssessment(
            assessment_state="collection_failed",
            review_concern_score=0,
            concern_band="low",
            evidence_coverage_score=0,
            headline="Forensic assessment could not be completed",
            summary=(
                "The evidence remains available in technical form, but the review "
                "assessment could not be generated. This is not evidence that the media is fake."
            ),
            limitations=_STANDARD_LIMITATIONS,
            scoring_method=SCORING_METHOD,
            scoring_version=SCORING_VERSION,
        )
    return evidence.model_copy(
        update={"schema_version": "1.2", "assessment": assessment}
    )
