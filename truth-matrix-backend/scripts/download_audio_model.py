from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from ml.audio_model_contract import (
    BACKEND_DIR,
    DEFAULT_MODEL_PATH,
    MODEL_REPO_ID,
    MODEL_REQUIRED_FILES,
    MODEL_REVISION,
    SNAPSHOT_METADATA_FILENAME,
    AudioSnapshotValidationError,
    validate_model_snapshot,
    validate_snapshot_files,
    write_snapshot_metadata,
)


class AudioModelSetupError(RuntimeError):
    """Raised when setup cannot safely produce a complete local snapshot."""


SnapshotDownload = Callable[..., str]


def _validate_destination(destination: Path) -> Path:
    path = destination.expanduser().resolve()
    filesystem_root = Path(path.anchor).resolve()
    if path == filesystem_root or path == BACKEND_DIR.resolve():
        raise AudioModelSetupError("Refusing to use a broad directory as the model destination")
    if path.exists() and not path.is_dir():
        raise AudioModelSetupError("The audio model destination exists and is not a directory")
    return path


def _remove_staging_directory(staging: Path, expected_parent: Path) -> None:
    resolved = staging.resolve()
    parent = expected_parent.resolve()
    if resolved.parent != parent or not resolved.name.startswith(".audio-model-staging-"):
        raise AudioModelSetupError("Refusing to remove an unexpected staging directory")
    if resolved.exists():
        shutil.rmtree(resolved)


def _prepare_existing_snapshot(destination: Path) -> Path:
    try:
        validate_snapshot_files(destination)
    except AudioSnapshotValidationError as exc:
        raise AudioModelSetupError(
            "The existing audio model destination is incomplete or does not match the pinned revision"
        ) from exc

    metadata_path = destination / SNAPSHOT_METADATA_FILENAME
    if not metadata_path.is_file():
        write_snapshot_metadata(destination)
    try:
        validate_model_snapshot(destination)
    except AudioSnapshotValidationError as exc:
        raise AudioModelSetupError(
            "The existing audio model metadata does not match the pinned revision"
        ) from exc
    return destination


def acquire_audio_model(
    destination: Path = DEFAULT_MODEL_PATH,
    *,
    snapshot_download: SnapshotDownload | None = None,
    verify_only: bool = False,
) -> Path:
    """Reuse a verified snapshot or atomically install a newly downloaded one."""
    target = _validate_destination(destination)
    if target.exists():
        return _prepare_existing_snapshot(target)
    if verify_only:
        raise AudioModelSetupError("The audio model snapshot is not installed")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".audio-model-staging-", dir=target.parent)
    ).resolve()
    try:
        if snapshot_download is None:
            from huggingface_hub import snapshot_download as registry_snapshot_download

            snapshot_download = registry_snapshot_download
        snapshot_download(
            repo_id=MODEL_REPO_ID,
            revision=MODEL_REVISION,
            local_dir=str(staging),
            allow_patterns=list(MODEL_REQUIRED_FILES),
            token=False,
        )
        validate_snapshot_files(staging)
        write_snapshot_metadata(staging)
        validate_model_snapshot(staging)

        registry_cache = staging / ".cache"
        if registry_cache.is_dir():
            shutil.rmtree(registry_cache)
        os.replace(staging, target)
        return target
    except AudioModelSetupError:
        raise
    except Exception as exc:
        raise AudioModelSetupError(
            "The pinned audio model snapshot could not be downloaded and verified"
        ) from exc
    finally:
        if staging.exists():
            _remove_staging_directory(staging, target.parent)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download and verify the pinned local audio model snapshot."
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Absolute path or path relative to the current shell.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing snapshot without downloading anything.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        installed = acquire_audio_model(
            args.destination,
            verify_only=args.verify_only,
        )
    except AudioModelSetupError as exc:
        print(f"Audio model setup failed: {exc}")
        return 1
    print(f"Audio model snapshot ready: {installed}")
    print(f"Pinned revision: {MODEL_REVISION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
