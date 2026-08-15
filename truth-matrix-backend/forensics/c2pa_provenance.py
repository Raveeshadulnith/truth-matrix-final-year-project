from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from urllib.parse import urlsplit

from schemas.forensic_schema import (
    C2paAction,
    C2paEvidence,
    C2paProvenanceConclusion,
)


CLASSIFICATION_METHOD = "c2pa-active-manifest-digital-source-type"
CLASSIFICATION_VERSION = "1.0"

_LIMITATIONS = [
    "Content Credentials verify a signed provenance declaration; they do not prove that the depicted claim is true.",
    "The credential does not establish ownership, intent, or whether the media is presented in the correct context.",
]

_SOURCE_CATEGORY = {
    "trainedAlgorithmicMedia": "ai_generated",
    "compositeWithTrainedAlgorithmicMedia": "ai_edited",
    "digitalCapture": "camera_capture",
    "computationalCapture": "camera_capture",
    "screenCapture": "screen_capture",
    "humanEdits": "human_edited",
    "digitalCreation": "digital_creation",
    "compositeSynthetic": "mixed_or_synthetic",
}

_VERIFIED_STATE = {
    "ai_generated": "verified_ai_generated",
    "ai_edited": "verified_ai_edited",
    "camera_capture": "verified_camera_capture",
    "screen_capture": "verified_screen_capture",
    "human_edited": "verified_human_edited",
    "digital_creation": "verified_digital_creation",
    "mixed_or_synthetic": "verified_mixed_or_synthetic",
}

_CATEGORY_COPY = {
    "ai_generated": ("AI-generated origin", "created using Generative AI"),
    "ai_edited": ("AI-assisted editing", "edited using Generative AI"),
    "camera_capture": ("Camera capture", "captured from a real-life source"),
    "screen_capture": ("Screen capture", "created as a screen capture"),
    "human_edited": ("Human editing history", "edited using non-generative tools"),
    "digital_creation": ("Digital creation", "created by a human using non-generative digital tools"),
    "mixed_or_synthetic": ("Mixed or synthetic composition", "composited with synthetic elements"),
}


@dataclass(frozen=True)
class _DeclaredAction:
    """One recognized controlled declaration with its active-manifest position."""

    index: int
    action: C2paAction
    terminal_source_type: str
    category: str


def _terminal_source_type(value: Optional[str]) -> Optional[str]:
    """Return an exact vocabulary terminal without substring guessing."""
    if not value:
        return None
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        return None
    parsed = urlsplit(cleaned)
    if parsed.scheme:
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or parsed.netloc.lower() != "cv.iptc.org"
            or not parsed.path.startswith("/newscodes/digitalsourcetype/")
        ):
            return None
        terminal = parsed.path.rsplit("/", 1)[-1]
    else:
        terminal = cleaned
    if terminal == "compositedWithTrainedAlgorithmicMedia":
        # Compatibility alias used by older C2PA guidance and fixtures.
        terminal = "compositeWithTrainedAlgorithmicMedia"
    return terminal if terminal in _SOURCE_CATEGORY else None


def _recognized_actions(actions: Iterable[C2paAction]) -> list[_DeclaredAction]:
    output: list[_DeclaredAction] = []
    seen: set[tuple[str, str, Optional[str], Optional[str]]] = set()
    for index, action in enumerate(actions):
        terminal = _terminal_source_type(action.digital_source_type)
        if terminal is None:
            continue
        key = (action.action, terminal, action.software_agent, action.description)
        if key in seen:
            continue
        seen.add(key)
        output.append(
            _DeclaredAction(index, action, terminal, _SOURCE_CATEGORY[terminal])
        )
    return output


def _is_creation_action(action: str) -> bool:
    return action.strip().lower().rsplit(".", 1)[-1] in {"created", "create"}


def _select_declaration(actions: Sequence[C2paAction]) -> Optional[_DeclaredAction]:
    """Select the final-asset declaration while retaining deterministic order."""
    recognized = _recognized_actions(actions)
    if not recognized:
        return None
    creations = [item for item in recognized if _is_creation_action(item.action.action)]
    generated_creation = next(
        (item for item in creations if item.category == "ai_generated"), None
    )
    if generated_creation is not None:
        return generated_creation
    if creations:
        creation = creations[0]
        later_ai_edit = next(
            (
                item
                for item in recognized
                if item.index > creation.index
                and item.category in {"ai_edited", "mixed_or_synthetic"}
            ),
            None,
        )
        return later_ai_edit or creation
    ai_generated = next(
        (item for item in recognized if item.category == "ai_generated"), None
    )
    if ai_generated is not None:
        return ai_generated
    return recognized[0]


def _provider(
    declaration: Optional[_DeclaredAction],
    claim_generator: Optional[str],
    signer: Optional[str],
) -> Optional[str]:
    if declaration and declaration.action.software_agent:
        return declaration.action.software_agent
    return claim_generator or signer


def _conclusion(
    *,
    origin_state: str,
    origin_category: str,
    basis_strength: str,
    headline: str,
    user_message: str,
    declaration: Optional[_DeclaredAction],
    claim_generator: Optional[str],
    signer: Optional[str],
) -> C2paProvenanceConclusion:
    provider = _provider(declaration, claim_generator, signer)
    references = ["c2pa.validation_state", "c2pa.signature_state", "c2pa.trust_state"]
    if declaration is not None:
        references.extend(
            [
                f"c2pa.actions[{declaration.index}].action",
                f"c2pa.actions[{declaration.index}].digital_source_type",
            ]
        )
    return C2paProvenanceConclusion(
        origin_state=origin_state,
        origin_category=origin_category,
        basis_strength=basis_strength,
        provider=provider,
        claim_generator=claim_generator,
        signer=signer,
        source_action=declaration.action.action if declaration else None,
        digital_source_type=(
            declaration.action.digital_source_type if declaration else None
        ),
        headline=headline,
        user_message=user_message,
        technical_references=references,
        limitations=_LIMITATIONS,
        classification_method=CLASSIFICATION_METHOD,
        classification_version=CLASSIFICATION_VERSION,
    )


def classify_c2pa_provenance(evidence: C2paEvidence) -> C2paProvenanceConclusion:
    """Classify bounded active-manifest evidence without using brand-name guesses."""
    if evidence.status.value in {"unsupported", "unavailable", "error"}:
        return _conclusion(
            origin_state="verification_unavailable",
            origin_category="unknown",
            basis_strength="unavailable",
            headline="Content Credentials verification unavailable",
            user_message="No reliable provenance conclusion could be reached from Content Credentials.",
            declaration=None,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )
    if not evidence.manifest_present or evidence.status.value == "not_present":
        return _conclusion(
            origin_state="no_origin_declaration",
            origin_category="unknown",
            basis_strength="none",
            headline="Content Credentials not attached",
            user_message="No Content Credentials were attached. This is common and does not indicate human or AI origin.",
            declaration=None,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )

    declaration = _select_declaration(evidence.actions)
    if (
        evidence.validation_state.value == "invalid"
        or evidence.signature_state.value == "invalid"
    ):
        return _conclusion(
            origin_state="invalid_credential",
            origin_category="unknown",
            basis_strength="invalid",
            headline="Invalid Content Credential",
            user_message="The credential or signed asset failed validation, so its origin declaration could not be verified.",
            declaration=declaration,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )

    cryptographically_valid = (
        evidence.validation_state.value == "valid"
        and evidence.signature_state.value == "valid"
    )
    trusted = cryptographically_valid and evidence.trust_state.value == "trusted"
    if not cryptographically_valid:
        return _conclusion(
            origin_state="unknown",
            origin_category=declaration.category if declaration else "unknown",
            basis_strength="unavailable",
            headline="Content Credentials origin unknown",
            user_message="A credential was present, but its signature and asset validation did not provide a reliable origin conclusion.",
            declaration=declaration,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )
    if declaration is None:
        return _conclusion(
            origin_state="no_origin_declaration",
            origin_category="unknown",
            basis_strength="valid_trusted" if trusted else "valid_untrusted",
            headline="Valid Content Credentials; origin type not specified",
            user_message="The credential is valid, but the active manifest does not declare a recognized origin type.",
            declaration=None,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )

    category = declaration.category
    label, phrase = _CATEGORY_COPY[category]
    provider = _provider(declaration, evidence.claim_generator, evidence.signer)
    attribution = f" by {provider}" if provider else ""
    if trusted:
        return _conclusion(
            origin_state=_VERIFIED_STATE[category],
            origin_category=category,
            basis_strength="valid_trusted",
            headline=f"Verified {label}",
            user_message=f"Content Credentials verify that this file was declared as {phrase}{attribution}.",
            declaration=declaration,
            claim_generator=evidence.claim_generator,
            signer=evidence.signer,
        )

    if category in {"ai_generated", "ai_edited"}:
        state = (
            "declared_ai_generated_untrusted"
            if category == "ai_generated"
            else "declared_ai_edited_untrusted"
        )
        headline = f"{label} declared; signer trust not established"
    else:
        state = "unknown"
        headline = f"{label} declared; signer trust not established"
    return _conclusion(
        origin_state=state,
        origin_category=category,
        basis_strength="valid_untrusted",
        headline=headline,
        user_message=f"The credential is cryptographically valid and declares that this file was {phrase}{attribution}, but the signer is not anchored in the configured trust store.",
        declaration=declaration,
        claim_generator=evidence.claim_generator,
        signer=evidence.signer,
    )
