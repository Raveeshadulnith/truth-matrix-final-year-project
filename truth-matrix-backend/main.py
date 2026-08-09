import logging
import math
import mimetypes
import os
from pathlib import Path
from shutil import copy2
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
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
from ml.audio_inference import analyze_audio
from ml.image_inference import analyze_image
from ml.video_inference import VideoInputError, analyze_video
from schemas.auth_schema import (
    AuthResponse,
    LoginRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
)
from schemas.response_schema import AnalysisResponse, ImageUrlRequest, VideoAnalysisResponse
from services.supabase_service import (
    delete_analysis_result,
    get_analysis_result_by_id,
    get_user_analysis_results,
    get_user_profile,
    save_analysis_result,
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
MAX_REMOTE_IMAGE_BYTES = int(os.getenv("MAX_REMOTE_IMAGE_BYTES", str(15 * 1024 * 1024)))
MAX_VIDEO_UPLOAD_BYTES = int(
    os.getenv("MAX_VIDEO_UPLOAD_BYTES", str(100 * 1024 * 1024))
)
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
    user_id: str,
    media_type: str,
    original_filename: str,
    local_url: Optional[str],
    analysis_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "media_type": media_type,
        "original_filename": original_filename,
        "firebase_url": local_url,
        "heatmap_url": analysis_result.get("heatmap_url"),
        "label": analysis_result["label"],
        "confidence": analysis_result["confidence"],
        "explanation": analysis_result.get("explanation"),
        "frames_analyzed": analysis_result.get("frames_analyzed"),
    }


def _format_analysis_response(
    analysis_result: Dict[str, Any],
    saved_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = dict(analysis_result)

    if saved_record:
        response.update(
            {
                "id": saved_record.get("id"),
                "firebase_url": saved_record.get("firebase_url"),
                "local_url": saved_record.get("firebase_url"),
                "heatmap_url": saved_record.get("heatmap_url") or analysis_result.get("heatmap_url"),
                "original_filename": saved_record.get("original_filename"),
                "saved_record": saved_record,
            }
        )

    return response


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

    try:
        bytes_written = await save_upload_file(
            file, temp_path, max_bytes=max_upload_bytes
        )
        if bytes_written == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        analysis_result = await run_in_threadpool(analyzer, str(temp_path))
        local_upload_name = _persist_local_file(
            temp_path,
            destination_dir=UPLOAD_DIR,
            media_type=media_type,
            filename=original_filename,
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
            except Exception as exc:
                logger.warning("[analyze] heatmap persistence failed: %s", exc)
            finally:
                remove_file_if_exists(heatmap_local)

        saved_record = save_analysis_result(
            _prepare_record(
                user_id=current_user["id"],
                media_type=media_type,
                original_filename=original_filename,
                local_url=local_url,
                analysis_result=analysis_result,
            )
        )
        return _format_analysis_response(analysis_result, saved_record)
    except HTTPException:
        raise
    except UploadTooLargeError as exc:
        limit_mb = max_upload_bytes / (1024 * 1024) if max_upload_bytes else 0
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {limit_mb:g} MB.",
        ) from exc
    except VideoInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        logger.exception("%s model file is unavailable", media_type.capitalize())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{media_type.capitalize()} analysis is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        logger.exception("%s analysis failed", media_type.capitalize())
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
    )


@app.post("/api/analyze/image-public", response_model=AnalysisResponse)
async def analyze_public_image_endpoint(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Unauthenticated image upload endpoint for the browser extension.

    It does not upload to Firebase or save into Supabase history; it only saves
    a temporary local file, runs the image model, and returns the same response
    shape as the authenticated image endpoint.
    """
    original_filename = file.filename or "extension-image.jpg"

    if not validate_extension(original_filename, IMAGE_EXTENSIONS):
        await file.close()
        allowed = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed extensions: {allowed}",
        )

    temp_path = _create_temp_upload_path(original_filename)

    try:
        await save_upload_file(file, temp_path)
        analysis_result = analyze_image(str(temp_path))
        analysis_result["original_filename"] = original_filename
        return analysis_result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image analysis failed: {exc}",
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


def _download_image_url_to_temp(image_url: str) -> Path:
    temp_path: Optional[Path] = None

    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": "TruthMatrix/1.0"},
            stream=True,
            timeout=(5, 20),
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if content_type and not content_type.lower().startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_url did not return an image response",
            )

        extension = _guess_remote_image_extension(image_url, content_type)
        temp_path = UPLOAD_DIR / generate_temp_filename(extension)

        downloaded_bytes = 0
        with temp_path.open("wb") as destination:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue

                downloaded_bytes += len(chunk)
                if downloaded_bytes > MAX_REMOTE_IMAGE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
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
            detail=f"Could not download image_url: {exc}",
        ) from exc
    finally:
        if "response" in locals():
            response.close()


@app.post("/api/analyze/image-url", response_model=AnalysisResponse)
def analyze_image_url_endpoint(payload: ImageUrlRequest) -> Dict[str, Any]:
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
    try:
        temp_path = _download_image_url_to_temp(image_url)
        return analyze_image(str(temp_path))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image URL analysis failed: {exc}",
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


@app.delete("/api/results/{result_id}")
def delete_result(
    result_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    deleted = delete_analysis_result(result_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found")
    return {"message": "Result deleted successfully", "deleted": deleted}
