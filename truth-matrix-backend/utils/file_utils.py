from pathlib import Path
from typing import Iterable, Union
from uuid import uuid4

from fastapi import UploadFile


PathLike = Union[str, Path]


class UploadTooLargeError(ValueError):
    """Raised when a streamed upload exceeds its configured byte limit."""


def get_file_extension(filename: str) -> str:
    """Return a lowercase file extension without the dot."""
    return Path(filename or "").suffix.lower().lstrip(".")


def validate_extension(filename: str, allowed_extensions: Iterable[str]) -> bool:
    """Check whether a filename has one of the allowed extensions."""
    extension = get_file_extension(filename)
    normalized_allowed = {item.lower().lstrip(".") for item in allowed_extensions}
    return bool(extension) and extension in normalized_allowed


def generate_temp_filename(extension: str) -> str:
    """Create a unique temporary filename using the supplied extension."""
    clean_extension = extension.lower().lstrip(".")
    return f"{uuid4().hex}.{clean_extension}"


async def save_upload_file(
    upload_file: UploadFile,
    destination_path: PathLike,
    *,
    max_bytes: int | None = None,
) -> int:
    """Save an uploaded file in chunks so large files do not fill memory."""
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    bytes_written = 0

    try:
        with destination.open("wb") as output_file:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if max_bytes is not None and bytes_written > max_bytes:
                    raise UploadTooLargeError(
                        f"Upload exceeds the {max_bytes}-byte limit"
                    )
                output_file.write(chunk)
        return bytes_written
    except Exception:
        remove_file_if_exists(destination)
        raise
    finally:
        await upload_file.close()


def remove_file_if_exists(path: PathLike) -> None:
    """Remove a file if it exists. Missing files are ignored."""
    file_path = Path(path)
    if file_path.exists() and file_path.is_file():
        file_path.unlink()
