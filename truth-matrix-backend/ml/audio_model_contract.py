from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "Audio-Detection"

MODEL_REPO_ID = "as1605/Deepfake-audio-detection-V2"
MODEL_REVISION = "3aeb18add053e945dc69025147afab0d70fa0188"
MODEL_VERSION = f"{MODEL_REPO_ID}@{MODEL_REVISION[:7]}"
SNAPSHOT_METADATA_FILENAME = "audio_model_snapshot.json"

MODEL_FILE_CONTRACT: Mapping[str, Mapping[str, Any]] = {
    "config.json": {
        "size": 2565,
        "sha256": "b7c934282324e5d7238d3eac6f50fbea965a58d5be1006c4fd9e509616dfa7a3",
    },
    "preprocessor_config.json": {
        "size": 215,
        "sha256": "8cdfd65ff4115423185a1512bdae100e2e0cd744f5b322417429944aaafd0827",
    },
    "model.safetensors": {
        "size": 378302360,
        "sha256": "997d9ce59e63151d5e444a6fa7c863986d0e56d515f67321bd705ac3b01bc38c",
    },
}
MODEL_REQUIRED_FILES = tuple(MODEL_FILE_CONTRACT)


class AudioSnapshotValidationError(RuntimeError):
    pass


def resolve_model_path(configured: str | None = None) -> Path:
    raw = configured if configured is not None else os.getenv("AUDIO_MODEL_PATH", "")
    if not raw or not raw.strip():
        return DEFAULT_MODEL_PATH.resolve()
    path = Path(raw.strip()).expanduser()
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_snapshot_metadata() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "repo_id": MODEL_REPO_ID,
        "revision": MODEL_REVISION,
        "files": {
            name: {
                "size": int(contract["size"]),
                "sha256": str(contract["sha256"]),
            }
            for name, contract in MODEL_FILE_CONTRACT.items()
        },
    }


def validate_snapshot_files(model_path: Path) -> None:
    path = model_path.resolve()
    if not path.is_dir():
        raise AudioSnapshotValidationError("The local audio model directory is missing")

    for name, contract in MODEL_FILE_CONTRACT.items():
        file_path = path / name
        if not file_path.is_file():
            raise AudioSnapshotValidationError(
                f"The local audio model snapshot is missing {name}"
            )
        if file_path.stat().st_size != int(contract["size"]):
            raise AudioSnapshotValidationError(
                f"The local audio model snapshot has an invalid {name} size"
            )
        if sha256_file(file_path) != str(contract["sha256"]):
            raise AudioSnapshotValidationError(
                f"The local audio model snapshot has an invalid {name} checksum"
            )


def validate_snapshot_metadata(model_path: Path) -> None:
    metadata_path = model_path.resolve() / SNAPSHOT_METADATA_FILENAME
    if not metadata_path.is_file():
        raise AudioSnapshotValidationError(
            "The local audio model snapshot metadata is missing"
        )
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AudioSnapshotValidationError(
            "The local audio model snapshot metadata is invalid"
        ) from exc
    if metadata != expected_snapshot_metadata():
        raise AudioSnapshotValidationError(
            "The local audio model snapshot metadata does not match the pinned revision"
        )


def validate_model_snapshot(model_path: Path, *, require_metadata: bool = True) -> None:
    validate_snapshot_files(model_path)
    if require_metadata:
        validate_snapshot_metadata(model_path)


def write_snapshot_metadata(model_path: Path) -> Path:
    path = model_path.resolve()
    validate_snapshot_files(path)
    metadata_path = path / SNAPSHOT_METADATA_FILENAME
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{SNAPSHOT_METADATA_FILENAME}.",
        suffix=".tmp",
        dir=path,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(expected_snapshot_metadata(), stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_path, metadata_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return metadata_path
