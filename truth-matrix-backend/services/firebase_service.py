import mimetypes
import os
from pathlib import Path
from uuid import uuid4

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, storage

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True, encoding="utf-8-sig")

_MEDIA_FOLDERS = {
    "image": "truth-matrix/image",
    "video": "truth-matrix/video",
    "audio": "truth-matrix/audio",
}


def _resolve_service_account_path() -> Path:
    configured_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
    service_account_path = Path(configured_path)

    if not service_account_path.is_absolute():
        service_account_path = BASE_DIR / service_account_path

    return service_account_path


def initialize_firebase() -> None:
    """Initialize Firebase Admin SDK once for the whole FastAPI process."""
    if firebase_admin._apps:
        return

    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    service_account_path = _resolve_service_account_path()

    if not bucket_name:
        raise RuntimeError("FIREBASE_STORAGE_BUCKET is missing in backend .env")

    if not service_account_path.exists():
        raise RuntimeError(
            f"Firebase service account file not found: {service_account_path}"
        )

    cred = credentials.Certificate(str(service_account_path))
    firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})


def _safe_filename(filename: str) -> str:
    return Path(filename or "upload.bin").name.replace(" ", "_")


def _guess_content_type(file_path: str, original_filename: str) -> str:
    guessed_type, _ = mimetypes.guess_type(original_filename or file_path)
    return guessed_type or "application/octet-stream"


def _upload_to_folder(file_path: str, folder: str, original_filename: str) -> str:
    initialize_firebase()

    safe_name = _safe_filename(original_filename)
    destination_name = f"{folder}/{uuid4().hex}_{safe_name}"
    bucket = storage.bucket()
    blob = bucket.blob(destination_name)
    content_type = _guess_content_type(file_path, original_filename)

    blob.upload_from_filename(file_path, content_type=content_type)

    # Demo behavior: make files public so the frontend can preview them easily.
    # Production recommendation: keep files private and return signed URLs instead.
    blob.make_public()

    return blob.public_url


def upload_file_to_firebase(file_path: str, media_type: str, original_filename: str) -> str:
    folder = _MEDIA_FOLDERS.get(media_type)
    if not folder:
        raise ValueError("media_type must be one of image, video, audio")

    return _upload_to_folder(file_path, folder, original_filename)


def upload_heatmap_to_firebase(file_path: str, original_filename: str) -> str:
    return _upload_to_folder(file_path, "truth-matrix/heatmaps", original_filename)
