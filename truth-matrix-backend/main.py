import logging
import ipaddress
import math
import mimetypes
import os
import socket
import threading
from collections import defaultdict, deque
from pathlib import Path
from shutil import copy2
from functools import partial
from typing import Any, Callable, Dict, Optional
from urllib.parse import ParseResult, urljoin, urlparse, urlunparse
from uuid import uuid4

logger = logging.getLogger(__name__)

import requests
from requests.adapters import HTTPAdapter
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from auth.auth_dependency import get_current_user
from auth.auth_service import (
    login_user,
    refresh_user_session,
    send_password_reset,
    signup_user,
)
from forensics.orchestrator import collect_forensic_evidence
from forensics.precise_location import (
    ENCRYPTION_VERSION,
    PreciseLocation,
    coordinate_decimal_places,
    decrypt_location,
    encrypt_location,
    precise_location_enabled,
)
from forensics.assessment import attach_model_forensic_alignment
from forensics.similarity import (
    attach_similarity_result,
    search_user_similarity_matches,
)
from ml.audio_inference import (
    MODEL_VERSION as AUDIO_MODEL_VERSION,
    AudioBusyError,
    AudioLimitError,
    AudioModelUnavailableError,
    InvalidAudioError,
    analyze_audio,
    get_audio_model_readiness,
)
from ml.image_inference import (
    ImageModelUnavailableError,
    InvalidImageError,
    analyze_image,
    get_image_model_readiness,
)
from ml.video_inference import VideoInputError, analyze_video
from schemas.auth_schema import (
    AuthResponse,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from schemas.forensic_schema import ForensicEvidence
from schemas.response_schema import (
    AnalysisResponse,
    AudioModelReadinessResponse,
    ImageModelReadinessResponse,
    ImageUrlRequest,
    PreciseLocationResponse,
    VideoAnalysisResponse,
)
from services.supabase_service import (
    delete_analysis_result,
    get_analysis_result_by_id,
    get_sensitive_location_record,
    get_user_analysis_results,
    get_user_profile,
    save_analysis_result,
    save_sensitive_location,
    update_user_profile,
)
from utils.file_utils import (
    generate_temp_filename,
    get_file_extension,
    remove_file_if_exists,
    save_upload_file,
    UploadTooLargeError,
    validate_extension,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm"}
AUDIO_EXTENSIONS = {"wav", "mp3", "m4a"}


def _upload_limit(name: str, default_bytes: int) -> int:
    """Load a bounded upload limit without accepting zero or unlimited values."""
    try:
        value = int(os.getenv(name, str(default_bytes)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer byte count") from exc
    if not 1024 <= value <= 500 * 1024 * 1024:
        raise RuntimeError(f"{name} must be between 1024 and 524288000 bytes")
    return value


MAX_IMAGE_UPLOAD_BYTES = _upload_limit("MAX_IMAGE_UPLOAD_BYTES", 25 * 1024 * 1024)
MAX_AUDIO_UPLOAD_BYTES = _upload_limit("MAX_AUDIO_UPLOAD_BYTES", 50 * 1024 * 1024)
MAX_REMOTE_IMAGE_BYTES = min(
    max(int(os.getenv("MAX_REMOTE_IMAGE_BYTES", str(15 * 1024 * 1024))), 1024),
    50 * 1024 * 1024,
)
MAX_REMOTE_IMAGE_REDIRECTS = min(
    max(int(os.getenv("MAX_REMOTE_IMAGE_REDIRECTS", "3")), 0),
    5,
)
MAX_VIDEO_UPLOAD_BYTES = _upload_limit("MAX_VIDEO_UPLOAD_BYTES", 100 * 1024 * 1024)
MAX_VIDEO_SEGMENT_SECONDS = float(os.getenv("MAX_VIDEO_SEGMENT_SECONDS", "30"))
VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/x-matroska",
    "video/quicktime",
    "video/avi",
    "video/msvideo",
    "video/x-ms-video",
    "video/x-msvideo",
    "application/octet-stream",
}
AUDIO_CONTENT_TYPES = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "audio/aac",
    "audio/mp4a-latm",
    "application/octet-stream",
}

_EXPECTED_MEDIA_MIME_PREFIX = {
    "image": "image/",
    "video": "video/",
    "audio": "audio/",
}

_location_rate_lock = threading.Lock()
_location_rate_events: Dict[str, deque[float]] = defaultdict(deque)


def _location_reveal_rate_limit() -> int:
    """Load the bounded per-user precise-location reveal limit."""
    try:
        value = int(os.getenv("LOCATION_REVEAL_RATE_LIMIT_PER_MINUTE", "5"))
    except ValueError as exc:
        raise RuntimeError("LOCATION_REVEAL_RATE_LIMIT_PER_MINUTE must be an integer") from exc
    if not 1 <= value <= 60:
        raise RuntimeError("LOCATION_REVEAL_RATE_LIMIT_PER_MINUTE must be between 1 and 60")
    return value


def _check_location_reveal_rate(user_id: str) -> None:
    """Apply a bounded in-process rate limit without recording coordinates."""
    from time import monotonic

    now = monotonic()
    cutoff = now - 60.0
    with _location_rate_lock:
        events = _location_rate_events[user_id]
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= _location_reveal_rate_limit():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many location reveal requests. Please wait and try again.",
                headers={"Cache-Control": "no-store", "Retry-After": "60"},
            )
        events.append(now)

app = FastAPI(
    title="Truth Matrix Deepfake Detection Backend",
    description="FastAPI backend for authenticated deepfake analysis and local file history.",
    version="1.0.0",
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
ALLOWED_ORIGINS = sorted(
    {
        FRONTEND_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


def _auth_error_detail(exc: Exception) -> tuple[int, str]:
    message = str(exc)
    lower_message = message.lower()

    if "email rate limit exceeded" in lower_message:
        return (
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Supabase is temporarily rate-limiting signup emails. Please wait a few minutes and try again, or disable email confirmations in Supabase Auth settings while developing locally.",
        )

    if "already registered" in lower_message or "already exists" in lower_message:
        return (
            status.HTTP_400_BAD_REQUEST,
            "An account with this email already exists. Please sign in instead.",
        )

    return status.HTTP_400_BAD_REQUEST, f"Signup failed: {message}"


@app.get("/")
def health_check() -> Dict[str, str]:
    return {"message": "Truth Matrix Deepfake Detection Backend is running"}


@app.get("/api/health/image-model", response_model=ImageModelReadinessResponse)
async def image_model_readiness() -> Dict[str, Any]:
    """Strictly validate the local image checkpoint without exposing its path."""
    try:
        return await run_in_threadpool(get_image_model_readiness)
    except Exception as exc:
        logger.exception("Image model readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image model is temporarily unavailable.",
        ) from exc


@app.get("/api/health/audio-model", response_model=AudioModelReadinessResponse)
async def audio_model_readiness(response: Response) -> Dict[str, Any]:
    """Validate the local audio runtime without exposing paths or diagnostics."""
    try:
        readiness = await run_in_threadpool(get_audio_model_readiness)
    except Exception as exc:
        logger.error(
            "Audio model readiness check failed unexpectedly",
            extra={"error_category": "unexpected", "error_type": type(exc).__name__},
        )
        readiness = {
            "status": "unavailable",
            "model_identifier": "deepfake-audio-detection-v2",
            "model_version": AUDIO_MODEL_VERSION,
            "device": None,
            "error_category": "unexpected",
        }
    if readiness["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return readiness


@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest) -> Dict[str, Any]:
    try:
        return signup_user(payload.full_name, payload.email, payload.password)
    except Exception as exc:
        error_status, detail = _auth_error_detail(exc)
        raise HTTPException(
            status_code=error_status,
            detail=detail,
        ) from exc


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> Dict[str, Any]:
    try:
        auth_response = login_user(payload.email, payload.password)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    if not auth_response.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login did not return an access token. Check Supabase email confirmation settings.",
        )

    return auth_response


@app.post("/api/auth/refresh", response_model=AuthResponse)
def refresh_session(payload: RefreshRequest) -> Dict[str, Any]:
    try:
        auth_response = refresh_user_session(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh the session. Please sign in again.",
        ) from exc

    if not auth_response.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session refresh did not return an access token.",
        )

    return auth_response


@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest) -> Dict[str, str]:
    try:
        send_password_reset(payload.email)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password reset failed: {exc}",
        ) from exc

    return {"message": "Password reset email sent"}


def _current_user_profile(current_user: Dict[str, Any]) -> Dict[str, Any]:
    profile = get_user_profile(current_user["id"]) or {}
    return {
        "id": current_user["id"],
        "email": profile.get("email") or current_user.get("email"),
        "full_name": profile.get("full_name") or "",
        "avatar_url": profile.get("avatar_url"),
        "role": profile.get("role") or "user",
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }


@app.get("/api/auth/me")
def read_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return _current_user_profile(current_user)


@app.put("/api/auth/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        update_user_profile(
            current_user["id"],
            {
                "full_name": payload.full_name,
                "avatar_url": payload.avatar_url,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile update failed: {exc}",
        ) from exc

    return _current_user_profile(current_user)


def _create_temp_upload_path(filename: str) -> Path:
    extension = get_file_extension(filename)
    return UPLOAD_DIR / generate_temp_filename(extension)


def _persist_local_file(source_path: Path, *, destination_dir: Path, media_type: str, filename: str) -> str:
    destination_name = f"{media_type}_{Path(filename or 'upload.bin').name.replace(' ', '_')}"
    destination = destination_dir / destination_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    copy2(source_path, destination)
    return destination_name


def _build_local_download_url(destination_name: str, route: str) -> str:
    return f"/{route}/{destination_name}"


def _prepare_record(
    *,
    analysis_id: Optional[str] = None,
    user_id: str,
    media_type: str,
    original_filename: str,
    local_url: Optional[str],
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    raw_forensic_evidence = analysis_result.get("forensic_evidence")
    forensic_evidence: Optional[Dict[str, Any]] = None

    if raw_forensic_evidence is not None:
        validated_evidence = (
            raw_forensic_evidence
            if isinstance(raw_forensic_evidence, ForensicEvidence)
            else ForensicEvidence.model_validate(raw_forensic_evidence)
        )
        forensic_evidence = validated_evidence.model_dump(mode="json")

    fingerprint = (
        forensic_evidence.get("perceptual_fingerprint", {})
        if forensic_evidence
        else {}
    )
    fingerprint_algorithm = fingerprint.get("algorithm")
    fingerprint_version = fingerprint.get("algorithm_version")
    if fingerprint_algorithm and fingerprint_version:
        fingerprint_algorithm = f"{fingerprint_algorithm}@{fingerprint_version}"

    record = {
        "user_id": user_id,
        "media_type": media_type,
        "original_filename": original_filename,
        "firebase_url": local_url,
        "heatmap_url": analysis_result.get("heatmap_url"),
        "label": analysis_result["label"],
        "confidence": analysis_result["confidence"],
        "fake_probability": analysis_result.get("fake_probability"),
        "authentic_probability": analysis_result.get("authentic_probability"),
        "model_version": analysis_result.get("model_version"),
        "explanation": analysis_result.get("explanation"),
        "frames_analyzed": analysis_result.get("frames_analyzed"),
        "sha256": forensic_evidence.get("sha256") if forensic_evidence else None,
        "perceptual_fingerprint": fingerprint.get("value"),
        "fingerprint_algorithm": fingerprint_algorithm,
        "forensic_evidence": forensic_evidence,
        "forensic_schema_version": (
            forensic_evidence.get("schema_version") if forensic_evidence else None
        ),
    }
    if analysis_id is not None:
        record["id"] = analysis_id
    return record


def _format_analysis_response(
    analysis_result: Dict[str, Any],
    saved_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = dict(analysis_result)

    if saved_record:
        stored_forensic_evidence = saved_record.get("forensic_evidence")
        response.update(
            {
                "id": saved_record.get("id"),
                "firebase_url": saved_record.get("firebase_url"),
                "local_url": saved_record.get("firebase_url"),
                "heatmap_url": saved_record.get("heatmap_url") or analysis_result.get("heatmap_url"),
                "original_filename": saved_record.get("original_filename"),
                "forensic_evidence": (
                    stored_forensic_evidence
                    if stored_forensic_evidence is not None
                    else analysis_result.get("forensic_evidence")
                ),
                "saved_record": saved_record,
            }
        )

    return response


def _attach_model_forensic_synthesis(
    analysis_result: Dict[str, Any],
    forensic_evidence: ForensicEvidence,
) -> ForensicEvidence:
    """Attach an independent alignment summary after model inference."""
    aligned_evidence, alignment = attach_model_forensic_alignment(
        forensic_evidence,
        analysis_result["label"],
    )
    analysis_result["forensic_evidence"] = aligned_evidence.model_dump(mode="json")
    analysis_result["model_forensic_alignment"] = alignment.model_dump(mode="json")
    return aligned_evidence


async def _collect_forensics(
    temp_path: Path,
    *,
    original_filename: str,
    declared_mime_type: Optional[str],
    analysis_id: str,
    private_location_sink: Optional[Callable[[PreciseLocation], None]] = None,
) -> ForensicEvidence:
    """Run all blocking forensic work off the event loop while the file exists."""
    return await run_in_threadpool(
        partial(
            collect_forensic_evidence,
            temp_path,
            original_filename=original_filename,
            declared_mime_type=declared_mime_type,
            allowed_root=UPLOAD_DIR,
            analysis_id=analysis_id,
            private_location_sink=private_location_sink,
        )
    )


async def _run_image_analysis(
    image_path: Path,
    analyzer: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run local image inference off-loop and translate its typed failures."""
    try:
        analysis_result = await run_in_threadpool(analyzer, str(image_path))
        AnalysisResponse.model_validate(analysis_result)
        return analysis_result
    except ImageModelUnavailableError as exc:
        logger.exception("Local image model is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image analysis is temporarily unavailable.",
        ) from exc
    except InvalidImageError as exc:
        logger.info("Image decoder rejected validated image bytes")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The image could not be decoded for analysis.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected local image inference failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image analysis failed. Please try again.",
        ) from exc


async def _run_audio_analysis(
    audio_path: Path,
    analyzer: Callable[[str], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run local audio inference off-loop and translate its typed failures."""
    try:
        analysis_result = await run_in_threadpool(analyzer, str(audio_path))
        AnalysisResponse.model_validate(analysis_result)
        return analysis_result
    except AudioBusyError as exc:
        logger.info("Audio inference capacity acquisition timed out")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Audio analysis capacity is busy. Please retry shortly.",
            headers={"Retry-After": "1"},
        ) from exc
    except AudioModelUnavailableError as exc:
        logger.error(
            "Local audio model is unavailable",
            extra={"error_category": "model_unavailable"},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio analysis is temporarily unavailable.",
        ) from exc
    except AudioLimitError as exc:
        logger.info("Audio decoder rejected an input that exceeded resource limits")
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The decoded audio exceeds the supported analysis limits.",
        ) from exc
    except InvalidAudioError as exc:
        logger.info("Audio decoder rejected validated audio bytes")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The audio could not be decoded into usable speech for analysis.",
        ) from exc
    except Exception as exc:
        logger.error(
            "Unexpected local audio inference failure",
            extra={"error_category": "inference_failed", "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audio analysis failed. Please try again.",
        ) from exc


async def _attach_authenticated_similarity(
    evidence: ForensicEvidence,
    *,
    user_id: str,
    analysis_id: str,
    media_type: str,
) -> ForensicEvidence:
    """Run bounded user-history matching outside the event loop."""
    result = await run_in_threadpool(
        partial(
            search_user_similarity_matches,
            user_id=user_id,
            current_analysis_id=analysis_id,
            media_type=media_type,
            evidence=evidence,
        )
    )
    logger.info(
        "forensic_extractor_timing",
        extra={
            "analysis_id": analysis_id,
            "extractor": "similarity",
            "status": result.status.value,
            "duration_ms": result.processing_time_ms,
        },
    )
    return attach_similarity_result(evidence, result)


def _require_detected_media_type(
    evidence: ForensicEvidence,
    expected_media_type: str,
) -> None:
    """Reject inputs whose byte-detected type cannot safely enter the model."""
    expected_prefix = _EXPECTED_MEDIA_MIME_PREFIX[expected_media_type]
    detected = evidence.detected_mime_type or ""
    if evidence.file_identity_status != "available" or not detected.startswith(
        expected_prefix
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The uploaded bytes are not a supported "
                f"{expected_media_type} file."
            ),
        )


async def _analyze_upload(
    *,
    file: UploadFile,
    media_type: str,
    allowed_extensions: set[str],
    analyzer: Callable[[str], Dict[str, Any]],
    current_user: Dict[str, Any],
    max_upload_bytes: Optional[int] = None,
    allowed_content_types: Optional[set[str]] = None,
) -> Dict[str, Any]:
    original_filename = file.filename or "upload"
    analysis_id = str(uuid4())

    if not validate_extension(original_filename, allowed_extensions):
        await file.close()
        allowed = ", ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed extensions: {allowed}",
        )

    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if allowed_content_types and content_type and content_type not in allowed_content_types:
        await file.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file content type does not match the selected media type.",
        )

    temp_path = _create_temp_upload_path(original_filename)
    private_locations: list[PreciseLocation] = []

    try:
        bytes_written = await save_upload_file(
            file, temp_path, max_bytes=max_upload_bytes
        )
        if bytes_written == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        forensic_evidence = await _collect_forensics(
            temp_path,
            original_filename=original_filename,
            declared_mime_type=content_type or None,
            analysis_id=analysis_id,
            private_location_sink=private_locations.append,
        )
        _require_detected_media_type(forensic_evidence, media_type)

        if media_type == "image":
            analysis_result = await _run_image_analysis(temp_path, analyzer)
        elif media_type == "audio":
            analysis_result = await _run_audio_analysis(temp_path, analyzer)
        else:
            analysis_result = await run_in_threadpool(analyzer, str(temp_path))
        forensic_evidence = await _attach_authenticated_similarity(
            forensic_evidence,
            user_id=current_user["id"],
            analysis_id=analysis_id,
            media_type=media_type,
        )
        forensic_evidence = _attach_model_forensic_synthesis(
            analysis_result, forensic_evidence
        )
        local_upload_name = await run_in_threadpool(
            partial(
                _persist_local_file,
                temp_path,
                destination_dir=UPLOAD_DIR,
                media_type=media_type,
                filename=original_filename,
            )
        )
        local_url = _build_local_download_url(local_upload_name, "uploads")
        analysis_result["local_url"] = local_url

        # Persist GradCAM heatmap produced by the ML layer (best-effort) locally.
        heatmap_local = analysis_result.pop("heatmap_path", None)
        if heatmap_local:
            try:
                heatmap_name = _persist_local_file(
                    Path(heatmap_local),
                    destination_dir=RESULTS_DIR,
                    media_type=f"{media_type}_heatmap",
                    filename=f"{media_type}_heatmap.png",
                )
                heatmap_url = _build_local_download_url(heatmap_name, "results")
                analysis_result["heatmap_url"] = heatmap_url
                logger.info("[analyze] local heatmap saved: %s", heatmap_url)
            except Exception:
                logger.warning("[analyze] heatmap persistence failed")
            finally:
                remove_file_if_exists(heatmap_local)

        saved_record = await run_in_threadpool(
            save_analysis_result,
            _prepare_record(
                analysis_id=analysis_id,
                user_id=current_user["id"],
                media_type=media_type,
                original_filename=original_filename,
                local_url=local_url,
                analysis_result=analysis_result,
            )
        )
        if private_locations:
            try:
                if precise_location_enabled():
                    encrypted_payload = encrypt_location(
                        private_locations[0],
                        analysis_id=analysis_id,
                        user_id=current_user["id"],
                    )
                    await run_in_threadpool(
                        partial(
                            save_sensitive_location,
                            analysis_id=analysis_id,
                            user_id=current_user["id"],
                            encrypted_payload=encrypted_payload,
                            encryption_version=ENCRYPTION_VERSION,
                        )
                    )
                else:
                    logger.info(
                        "precise location was detected but persistence is disabled",
                        extra={"analysis_id": analysis_id, "status": "disabled"},
                    )
            except Exception:
                logger.exception(
                    "precise location was not persisted",
                    extra={"analysis_id": analysis_id, "status": "unavailable"},
                )
        return _format_analysis_response(analysis_result, saved_record)
    except HTTPException:
        raise
    except UploadTooLargeError as exc:
        limit_mb = max_upload_bytes / (1024 * 1024) if max_upload_bytes else 0
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size is {limit_mb:g} MB.",
        ) from exc
    except VideoInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        logger.error("%s model file is unavailable", media_type.capitalize())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{media_type.capitalize()} analysis is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        logger.error("%s analysis failed", media_type.capitalize())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{media_type.capitalize()} analysis failed. Please try again.",
        ) from exc
    finally:
        remove_file_if_exists(temp_path)


@app.post("/api/analyze/image", response_model=AnalysisResponse)
async def analyze_image_endpoint(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return await _analyze_upload(
        file=file,
        media_type="image",
        allowed_extensions=IMAGE_EXTENSIONS,
        analyzer=analyze_image,
        current_user=current_user,
        max_upload_bytes=MAX_IMAGE_UPLOAD_BYTES,
    )


@app.post("/api/analyze/image-public", response_model=AnalysisResponse)
async def analyze_public_image_endpoint(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Unauthenticated image upload endpoint for the browser extension.

    It does not upload to Firebase or save into Supabase history; it only saves
    a temporary local file, runs the image model, and returns the same response
    shape as the authenticated image endpoint.
    """
    original_filename = file.filename or "extension-image.jpg"
    declared_mime_type = (file.content_type or "").split(";", 1)[0].strip() or None
    analysis_id = str(uuid4())

    if not validate_extension(original_filename, IMAGE_EXTENSIONS):
        await file.close()
        allowed = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed extensions: {allowed}",
        )

    temp_path = _create_temp_upload_path(original_filename)

    try:
        bytes_written = await save_upload_file(
            file, temp_path, max_bytes=MAX_IMAGE_UPLOAD_BYTES
        )
        if bytes_written == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )
        forensic_evidence = await _collect_forensics(
            temp_path,
            original_filename=original_filename,
            declared_mime_type=declared_mime_type,
            analysis_id=analysis_id,
        )
        _require_detected_media_type(forensic_evidence, "image")
        analysis_result = await _run_image_analysis(temp_path, analyze_image)
        analysis_result["original_filename"] = original_filename
        _attach_model_forensic_synthesis(analysis_result, forensic_evidence)
        return analysis_result
    except HTTPException:
        raise
    except UploadTooLargeError as exc:
        limit_mb = MAX_IMAGE_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size is {limit_mb:g} MB.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image analysis failed. Please try again.",
        ) from exc
    finally:
        remove_file_if_exists(temp_path)


@app.post("/api/analyze/video", response_model=VideoAnalysisResponse)
async def analyze_video_endpoint(
    file: UploadFile = File(...),
    segment_start_seconds: Optional[float] = Form(default=None),
    segment_duration_seconds: Optional[float] = Form(default=None),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if (segment_start_seconds is None) != (segment_duration_seconds is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video segment start and duration must be provided together.",
        )

    if segment_start_seconds is not None and segment_duration_seconds is not None:
        if not math.isfinite(segment_start_seconds) or segment_start_seconds < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video segment start must be a non-negative number.",
            )
        if (
            not math.isfinite(segment_duration_seconds)
            or segment_duration_seconds <= 0
            or segment_duration_seconds > MAX_VIDEO_SEGMENT_SECONDS
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video segment duration must be between 0 and {MAX_VIDEO_SEGMENT_SECONDS:g} seconds.",
            )

    def analyze_selected_segment(video_path: str) -> Dict[str, Any]:
        return analyze_video(
            video_path,
            segment_start_seconds=segment_start_seconds,
            segment_duration_seconds=segment_duration_seconds,
        )

    return await _analyze_upload(
        file=file,
        media_type="video",
        allowed_extensions=VIDEO_EXTENSIONS,
        analyzer=analyze_selected_segment,
        current_user=current_user,
        max_upload_bytes=MAX_VIDEO_UPLOAD_BYTES,
        allowed_content_types=VIDEO_CONTENT_TYPES,
    )


@app.post("/api/analyze/audio", response_model=AnalysisResponse)
async def analyze_audio_endpoint(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return await _analyze_upload(
        file=file,
        media_type="audio",
        allowed_extensions=AUDIO_EXTENSIONS,
        analyzer=analyze_audio,
        current_user=current_user,
        max_upload_bytes=MAX_AUDIO_UPLOAD_BYTES,
        allowed_content_types=AUDIO_CONTENT_TYPES,
    )


def _guess_remote_image_extension(image_url: str, content_type: str) -> str:
    clean_content_type = content_type.split(";", 1)[0].strip().lower()
    guessed_extension = (
        mimetypes.guess_extension(clean_content_type) if clean_content_type else None
    )

    if guessed_extension:
        extension = guessed_extension.lstrip(".").lower()
        if extension == "jpe":
            return "jpg"
        if extension in IMAGE_EXTENSIONS:
            return extension

    path_extension = get_file_extension(urlparse(image_url).path)
    if path_extension in IMAGE_EXTENSIONS:
        return path_extension

    return "jpg"


class _PinnedHttpsAdapter(HTTPAdapter):
    """Connect to a validated IP while retaining TLS SNI/hostname checks."""

    def __init__(self, server_hostname: str) -> None:
        self._server_hostname = server_hostname
        super().__init__()

    def init_poolmanager(
        self,
        connections: int,
        maxsize: int,
        block: bool = False,
        **pool_kwargs: Any,
    ) -> None:
        pool_kwargs["server_hostname"] = self._server_hostname
        pool_kwargs["assert_hostname"] = self._server_hostname
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)


def _resolve_public_remote_url(image_url: str) -> tuple[ParseResult, str]:
    """Resolve an HTTP(S) URL and return one validated, pinned public address."""
    parsed = urlparse(image_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url must be an absolute HTTP or HTTPS URL",
        )
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url must not include credentials",
        )
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        addresses = socket.getaddrinfo(
            parsed.hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url host could not be resolved safely",
        ) from exc
    if not addresses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url host did not resolve",
        )
    public_addresses: set[str] = set()
    for address in addresses:
        try:
            resolved_ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url resolved to an invalid address",
            ) from exc
        if not resolved_ip.is_global:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url may not resolve to a private or reserved address",
            )
        public_addresses.add(resolved_ip.compressed)
    return parsed, sorted(public_addresses)[0]


def _validate_public_remote_url(image_url: str) -> None:
    """Reject local, reserved, credentialed, or non-HTTP URL destinations."""
    _resolve_public_remote_url(image_url)


def _pinned_remote_url(parsed: ParseResult, address: str) -> str:
    host = f"[{address}]" if ":" in address else address
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=host))


def _download_image_url_to_temp(image_url: str) -> Path:
    temp_path: Optional[Path] = None
    response: Optional[requests.Response] = None
    session = requests.Session()
    session.trust_env = False

    try:
        current_url = image_url
        for redirect_count in range(MAX_REMOTE_IMAGE_REDIRECTS + 1):
            parsed_url, pinned_address = _resolve_public_remote_url(current_url)
            request_url = _pinned_remote_url(parsed_url, pinned_address)
            if parsed_url.scheme.lower() == "https":
                session.mount(
                    "https://",
                    _PinnedHttpsAdapter(parsed_url.hostname or ""),
                )
            host_header = parsed_url.hostname or ""
            if parsed_url.port is not None:
                host_header = f"{host_header}:{parsed_url.port}"
            response = session.get(
                request_url,
                headers={
                    "User-Agent": "TruthMatrix/1.0",
                    "Host": host_header,
                },
                stream=True,
                timeout=(5, 20),
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                if redirect_count >= MAX_REMOTE_IMAGE_REDIRECTS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="image_url exceeded the redirect limit",
                    )
                location = response.headers.get("location")
                response.close()
                response = None
                if not location:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="image_url returned an invalid redirect",
                    )
                current_url = urljoin(current_url, location)
                continue
            break
        if response is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url did not return a response",
            )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.lower().startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url did not return an image response",
            )

        extension = _guess_remote_image_extension(current_url, content_type)
        temp_path = UPLOAD_DIR / generate_temp_filename(extension)

        downloaded_bytes = 0
        with temp_path.open("wb") as destination:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue

                downloaded_bytes += len(chunk)
                if downloaded_bytes > MAX_REMOTE_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Remote image is too large to analyze",
                    )

                destination.write(chunk)

        if downloaded_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url returned an empty image response",
            )

        return temp_path
    except HTTPException:
        if temp_path:
            remove_file_if_exists(temp_path)
        raise
    except requests.RequestException as exc:
        if temp_path:
            remove_file_if_exists(temp_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not download image_url",
        ) from exc
    finally:
        if response is not None:
            response.close()
        session.close()


@app.post("/api/analyze/image-url", response_model=AnalysisResponse)
async def analyze_image_url_endpoint(payload: ImageUrlRequest) -> Dict[str, Any]:
    """Public endpoint for the browser extension.

    Downloads the remote image into temporary storage, runs the trained image
    model, then deletes the temporary file. This endpoint intentionally does not
    save public extension scans into authenticated user history.
    """
    image_url = payload.image_url.strip()

    if not image_url.lower().startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="image_url must start with http:// or https://",
        )

    temp_path: Optional[Path] = None
    analysis_id = str(uuid4())
    try:
        temp_path = await run_in_threadpool(_download_image_url_to_temp, image_url)
        original_filename = f"remote-image{temp_path.suffix.lower()}"
        forensic_evidence = await _collect_forensics(
            temp_path,
            original_filename=original_filename,
            declared_mime_type=None,
            analysis_id=analysis_id,
        )
        _require_detected_media_type(forensic_evidence, "image")
        analysis_result = await _run_image_analysis(temp_path, analyze_image)
        analysis_result["original_filename"] = original_filename
        _attach_model_forensic_synthesis(analysis_result, forensic_evidence)
        return analysis_result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Image URL analysis failed. Please try again.",
        ) from exc
    finally:
        if temp_path:
            remove_file_if_exists(temp_path)


@app.get("/api/results")
def list_results(
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = 50,
) -> Dict[str, Any]:
    safe_limit = min(max(limit, 1), 100)
    return {
        "results": get_user_analysis_results(current_user["id"], safe_limit),
    }


@app.get("/api/results/{result_id}")
def read_result(
    result_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    result = get_analysis_result_by_id(result_id, current_user["id"])
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return result


@app.get(
    "/api/analyses/{analysis_id}/precise-location",
    response_model=PreciseLocationResponse,
)
def read_precise_location(
    analysis_id: str,
    response: Response,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Reveal encrypted embedded coordinates only to the analysis owner."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    _check_location_reveal_rate(current_user["id"])

    try:
        analysis = get_analysis_result_by_id(analysis_id, current_user["id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Precise location is temporarily unavailable.",
            headers={"Cache-Control": "no-store"},
        ) from exc
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
            headers={"Cache-Control": "no-store"},
        )
    if not precise_location_enabled():
        return {"status": "unavailable"}
    try:
        private_record = get_sensitive_location_record(analysis_id, current_user["id"])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Precise location is temporarily unavailable.",
            headers={"Cache-Control": "no-store"},
        ) from exc
    if not private_record:
        forensic = analysis.get("forensic_evidence")
        creation = forensic.get("creation_info") if isinstance(forensic, dict) else None
        location_present = creation.get("location_present") if isinstance(creation, dict) else False
        return {"status": "unavailable" if location_present else "not_present"}
    if private_record.get("encryption_version") != ENCRYPTION_VERSION:
        return {"status": "unavailable"}

    try:
        location = decrypt_location(
            str(private_record.get("encrypted_payload") or ""),
            analysis_id=analysis_id,
            user_id=current_user["id"],
        )
    except ValueError:
        return {"status": "invalid"}

    precision = coordinate_decimal_places()
    return {
        "status": "available",
        "latitude": round(location.latitude, precision),
        "longitude": round(location.longitude, precision),
        "altitude_meters": location.altitude_meters,
        "source": location.source,
        "accuracy_meters": location.accuracy_meters,
    }


@app.delete("/api/results/{result_id}")
def delete_result(
    result_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    deleted = delete_analysis_result(result_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return {"message": "Result deleted successfully", "deleted": deleted}
