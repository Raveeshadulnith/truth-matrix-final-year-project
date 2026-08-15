from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np

from ml.audio_model_contract import (
    DEFAULT_MODEL_PATH,
    MODEL_REPO_ID,
    MODEL_REVISION,
    MODEL_VERSION,
    AudioSnapshotValidationError,
    resolve_model_path,
    validate_snapshot_files,
    validate_snapshot_metadata,
    validate_model_snapshot,
)

logger = logging.getLogger(__name__)

MODEL_ID = MODEL_REPO_ID

TARGET_SAMPLE_RATE = 16_000
DEFAULT_MAX_SOURCE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_DECODE_SECONDS = 300.0
DEFAULT_CHUNK_SECONDS = 10.0
DEFAULT_CHUNK_OVERLAP_SECONDS = 1.0
DEFAULT_MIN_AUDIO_SECONDS = 0.25
DEFAULT_DECODER_TIMEOUT_SECONDS = 30.0
DEFAULT_SILENCE_RMS_THRESHOLD = 1e-5
DEFAULT_MAX_CONCURRENT_INFERENCES = 1
DEFAULT_INFERENCE_ACQUIRE_TIMEOUT_SECONDS = 1.0
DECODER_STDERR_MAX_BYTES = 8 * 1024
DECODER_READ_BLOCK_BYTES = 64 * 1024
PROBABILITY_SUM_TOLERANCE = 1e-5
EXPECTED_ARCHITECTURE = "Wav2Vec2ForSequenceClassification"
PUBLIC_MODEL_IDENTIFIER = "deepfake-audio-detection-v2"


class AudioModelUnavailableError(RuntimeError):
    pass


class InvalidAudioError(ValueError):
    pass


class AudioLimitError(ValueError):
    pass


class AudioBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class _ModelBundle:
    model: Any
    feature_extractor: Any
    torch: Any
    device: Any
    model_path: Path


@dataclass(frozen=True)
class _RuntimeConfig:
    model_path: Path
    revision: str
    max_source_bytes: int
    max_decode_seconds: float
    chunk_samples: int
    overlap_samples: int
    minimum_samples: int
    decoder_timeout_seconds: float
    silence_threshold: float
    ffmpeg_path: str
    warmup_enabled: bool
    max_concurrent_inferences: int
    inference_acquire_timeout_seconds: float


@dataclass(frozen=True)
class _DecoderResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    stdout_limit_exceeded: bool = False


@dataclass
class _AudioReadinessState:
    model_files_present: bool = False
    pinned_revision_verified: bool = False
    config_mapping_valid: bool = False
    feature_extractor_valid: bool = False
    decoder_available: bool = False
    selected_device: str = "unknown"
    warmup_status: str = "not_run"
    error_category: str | None = None


_model_bundle: _ModelBundle | None = None
_model_cache_key: Tuple[str, str, str] | None = None
_runtime_config: _RuntimeConfig | None = None
_inference_semaphore: threading.BoundedSemaphore | None = None
_inference_semaphore_size: int | None = None
_last_readiness_state: _AudioReadinessState | None = None
_load_lock = threading.Lock()
_config_lock = threading.Lock()
_predict_lock = threading.Lock()
_semaphore_lock = threading.Lock()
_readiness_state_lock = threading.Lock()
_readiness_check_lock = threading.Lock()


def _log_timing(
    stage: str,
    duration_seconds: float,
    *,
    status: str = "success",
    operation: str = "analysis",
    **safe_fields: Any,
) -> None:
    logger.info(
        "audio_inference_timing",
        extra={
            "event": "audio_inference_timing",
            "stage": stage,
            "duration_ms": round(max(duration_seconds, 0.0) * 1000.0, 3),
            "status": status,
            "operation": operation,
            **safe_fields,
        },
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise AudioModelUnavailableError(f"{name} must be true or false")


def _env_float(
    name: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise AudioModelUnavailableError(f"{name} must be a number") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise AudioModelUnavailableError(
            f"{name} must be between {minimum:g} and {maximum:g}"
        )
    return value


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise AudioModelUnavailableError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise AudioModelUnavailableError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


def _load_runtime_config() -> _RuntimeConfig:
    global _runtime_config
    if _runtime_config is not None:
        return _runtime_config

    with _config_lock:
        if _runtime_config is not None:
            return _runtime_config

        configured_revision = os.getenv("AUDIO_MODEL_REVISION", MODEL_REVISION).strip()
        if configured_revision != MODEL_REVISION:
            raise AudioModelUnavailableError(
                "AUDIO_MODEL_REVISION does not match the pinned production revision"
            )

        chunk_seconds = _env_float(
            "AUDIO_CHUNK_SECONDS",
            DEFAULT_CHUNK_SECONDS,
            minimum=1.0,
            maximum=30.0,
        )
        overlap_seconds = _env_float(
            "AUDIO_CHUNK_OVERLAP_SECONDS",
            DEFAULT_CHUNK_OVERLAP_SECONDS,
            minimum=0.0,
            maximum=10.0,
        )
        if overlap_seconds >= chunk_seconds:
            raise AudioModelUnavailableError(
                "AUDIO_CHUNK_OVERLAP_SECONDS must be smaller than AUDIO_CHUNK_SECONDS"
            )

        _runtime_config = _RuntimeConfig(
            model_path=resolve_model_path(),
            revision=configured_revision,
            max_source_bytes=_env_int(
                "AUDIO_MODEL_MAX_SOURCE_BYTES",
                DEFAULT_MAX_SOURCE_BYTES,
                minimum=1024,
                maximum=500 * 1024 * 1024,
            ),
            max_decode_seconds=_env_float(
                "AUDIO_MAX_DECODE_SECONDS",
                DEFAULT_MAX_DECODE_SECONDS,
                minimum=1.0,
                maximum=600.0,
            ),
            chunk_samples=round(chunk_seconds * TARGET_SAMPLE_RATE),
            overlap_samples=round(overlap_seconds * TARGET_SAMPLE_RATE),
            minimum_samples=round(
                _env_float(
                    "AUDIO_MIN_SECONDS",
                    DEFAULT_MIN_AUDIO_SECONDS,
                    minimum=0.05,
                    maximum=2.0,
                )
                * TARGET_SAMPLE_RATE
            ),
            decoder_timeout_seconds=_env_float(
                "AUDIO_DECODER_TIMEOUT_SECONDS",
                DEFAULT_DECODER_TIMEOUT_SECONDS,
                minimum=1.0,
                maximum=120.0,
            ),
            silence_threshold=_env_float(
                "AUDIO_SILENCE_RMS_THRESHOLD",
                DEFAULT_SILENCE_RMS_THRESHOLD,
                minimum=0.0,
                maximum=0.1,
            ),
            ffmpeg_path=os.getenv("FFMPEG_PATH", "").strip(),
            warmup_enabled=_env_bool("AUDIO_MODEL_WARMUP_ENABLED", False),
            max_concurrent_inferences=_env_int(
                "AUDIO_MAX_CONCURRENT_INFERENCES",
                DEFAULT_MAX_CONCURRENT_INFERENCES,
                minimum=1,
                maximum=8,
            ),
            inference_acquire_timeout_seconds=_env_float(
                "AUDIO_INFERENCE_ACQUIRE_TIMEOUT_SECONDS",
                DEFAULT_INFERENCE_ACQUIRE_TIMEOUT_SECONDS,
                minimum=0.05,
                maximum=30.0,
            ),
        )
        return _runtime_config


def _max_source_bytes() -> int:
    return _load_runtime_config().max_source_bytes


def _max_decode_seconds() -> float:
    return _load_runtime_config().max_decode_seconds


def _chunk_settings() -> Tuple[int, int]:
    config = _load_runtime_config()
    return config.chunk_samples, config.overlap_samples


def _minimum_samples() -> int:
    return _load_runtime_config().minimum_samples


def _decoder_timeout_seconds() -> float:
    return _load_runtime_config().decoder_timeout_seconds


def _silence_threshold() -> float:
    return _load_runtime_config().silence_threshold


def _configured_revision() -> str:
    return _load_runtime_config().revision


def _resolve_model_path() -> Path:
    return _load_runtime_config().model_path


def _validate_model_files(model_path: Path) -> None:
    try:
        validate_model_snapshot(model_path)
    except AudioSnapshotValidationError as exc:
        raise AudioModelUnavailableError(str(exc)) from exc


def _normalised_label_map(config: Any) -> Dict[int, str]:
    try:
        return {int(key): str(value).strip().lower() for key, value in config.id2label.items()}
    except (AttributeError, TypeError, ValueError) as exc:
        raise AudioModelUnavailableError("The audio model class mapping is invalid") from exc


def _validate_loaded_contract(model: Any, feature_extractor: Any) -> None:
    config = getattr(model, "config", None)
    architectures = getattr(config, "architectures", None)
    if not isinstance(architectures, (list, tuple)) or EXPECTED_ARCHITECTURE not in {
        str(name) for name in architectures
    }:
        raise AudioModelUnavailableError(
            "The audio model architecture is not compatible with sequence classification"
        )

    label_map = _normalised_label_map(config)
    if getattr(config, "num_labels", None) != 2 or label_map != {
        0: "fake",
        1: "real",
    }:
        raise AudioModelUnavailableError(
            "The audio model does not have the required 0=fake, 1=real mapping"
        )
    if int(getattr(feature_extractor, "sampling_rate", 0)) != TARGET_SAMPLE_RATE:
        raise AudioModelUnavailableError("The audio model does not expect 16 kHz input")
    if not bool(getattr(feature_extractor, "do_normalize", False)):
        raise AudioModelUnavailableError(
            "The audio model feature extractor must normalize its waveform input"
        )


def _load_model_bundle(*, snapshot_validated: bool = False) -> _ModelBundle:
    global _model_bundle, _model_cache_key

    model_path = _resolve_model_path()
    revision = _configured_revision()
    try:
        import torch
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    except ImportError as exc:
        raise AudioModelUnavailableError(
            "The local audio model runtime dependencies are unavailable"
        ) from exc

    try:
        device_name = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception as exc:
        raise AudioModelUnavailableError(
            "The audio inference device could not be inspected"
        ) from exc
    cache_key = (str(model_path), revision, device_name)
    if _model_bundle is not None and _model_cache_key == cache_key:
        return _model_bundle

    with _load_lock:
        if _model_bundle is not None and _model_cache_key == cache_key:
            return _model_bundle

        if not snapshot_validated:
            _validate_model_files(model_path)
        try:
            feature_extractor = AutoFeatureExtractor.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
            )
            model = AutoModelForAudioClassification.from_pretrained(
                model_path,
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=True,
            )
        except Exception as exc:
            raise AudioModelUnavailableError(
                "The pinned local audio model could not be loaded"
            ) from exc

        _validate_loaded_contract(model, feature_extractor)
        try:
            device = torch.device(device_name)
            model.to(device)
            model.eval()
        except Exception as exc:
            raise AudioModelUnavailableError(
                "The audio inference device could not be initialized"
            ) from exc
        bundle = _ModelBundle(
            model=model,
            feature_extractor=feature_extractor,
            torch=torch,
            device=device,
            model_path=model_path,
        )
        _model_bundle = bundle
        _model_cache_key = cache_key
        logger.info("Pinned local audio model ready on %s", device_name)
        return bundle


def _reset_model_cache_for_tests() -> None:
    global _model_bundle, _model_cache_key, _runtime_config
    global _inference_semaphore, _inference_semaphore_size, _last_readiness_state
    with _load_lock:
        _model_bundle = None
        _model_cache_key = None
    with _config_lock:
        _runtime_config = None
    with _semaphore_lock:
        _inference_semaphore = None
        _inference_semaphore_size = None
    with _readiness_state_lock:
        _last_readiness_state = None


def _resolve_decoder() -> str:
    configured = _load_runtime_config().ffmpeg_path
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.is_file():
            raise AudioModelUnavailableError("The configured audio decoder is missing")
        return str(path)

    system_decoder = shutil.which("ffmpeg")
    if system_decoder:
        return system_decoder

    try:
        import imageio_ffmpeg

        bundled_decoder = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    except (ImportError, RuntimeError) as exc:
        raise AudioModelUnavailableError("No supported audio decoder is installed") from exc
    if not bundled_decoder.is_file():
        raise AudioModelUnavailableError("No supported audio decoder is installed")
    return str(bundled_decoder)


def _store_readiness_state(state: _AudioReadinessState) -> None:
    global _last_readiness_state
    with _readiness_state_lock:
        _last_readiness_state = _AudioReadinessState(**asdict(state))


def _get_last_audio_readiness_state_for_tests() -> Dict[str, Any] | None:
    with _readiness_state_lock:
        return asdict(_last_readiness_state) if _last_readiness_state else None


def _safe_readiness_result(
    *,
    status: str,
    device: str | None,
    error_category: str | None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "model_identifier": PUBLIC_MODEL_IDENTIFIER,
        "model_version": MODEL_VERSION,
        "device": device,
        "error_category": error_category,
    }


def _run_readiness_warmup(bundle: _ModelBundle) -> None:
    sample_count = max(TARGET_SAMPLE_RATE, _minimum_samples())
    times = np.arange(sample_count, dtype=np.float32) / TARGET_SAMPLE_RATE
    waveform = (0.01 * np.sin(2.0 * np.pi * 220.0 * times)).astype(np.float32)
    probabilities, chunk_count = _predict_probabilities(
        [(waveform, sample_count)],
        bundle,
        operation="warmup",
    )
    if chunk_count != 1 or probabilities.shape != (2,):
        raise AudioModelUnavailableError("Audio model warmup returned an invalid result")


def _readiness_error_category(stage: str, exc: Exception) -> str:
    message = str(exc).lower()
    if stage == "configuration":
        return "configuration_invalid"
    if stage == "model_files":
        return "model_files_invalid"
    if stage == "revision":
        return "revision_invalid"
    if stage == "decoder":
        return "decoder_unavailable"
    if stage == "model_load":
        if "class mapping" in message or "architecture" in message or "0=fake" in message:
            return "model_contract_invalid"
        if "16 khz" in message or "normalize" in message or "feature extractor" in message:
            return "feature_extractor_invalid"
        if "device" in message or "cuda" in message:
            return "device_unavailable"
        return "model_load_failed"
    if stage == "warmup":
        return "warmup_failed"
    return "unexpected"


def _evaluate_audio_model_readiness() -> Dict[str, Any]:
    state = _AudioReadinessState()
    stage = "configuration"
    try:
        config = _load_runtime_config()

        stage = "model_files"
        validate_snapshot_files(config.model_path)
        state.model_files_present = True

        stage = "revision"
        validate_snapshot_metadata(config.model_path)
        state.pinned_revision_verified = True

        stage = "decoder"
        _resolve_decoder()
        state.decoder_available = True

        stage = "model_load"
        model_load_started = time.perf_counter()
        try:
            bundle = _load_model_bundle(snapshot_validated=True)
        except Exception:
            _log_timing(
                "model_load",
                time.perf_counter() - model_load_started,
                status="error",
                operation="readiness",
            )
            raise
        _log_timing(
            "model_load",
            time.perf_counter() - model_load_started,
            operation="readiness",
            device=str(bundle.device).split(":", 1)[0],
        )
        state.config_mapping_valid = True
        state.feature_extractor_valid = True
        device = str(bundle.device).split(":", 1)[0]
        state.selected_device = device if device in {"cpu", "cuda"} else "unknown"

        if config.warmup_enabled:
            stage = "warmup"
            _run_readiness_warmup(bundle)
            state.warmup_status = "successful"
        else:
            state.warmup_status = "disabled"

        _store_readiness_state(state)
        logger.info("audio_model_readiness", extra={"event": "audio_model_readiness", **asdict(state)})
        return _safe_readiness_result(
            status="ready",
            device=state.selected_device,
            error_category=None,
        )
    except Exception as exc:
        state.error_category = _readiness_error_category(stage, exc)
        if stage == "warmup":
            state.warmup_status = "failed"
        _store_readiness_state(state)
        logger.error(
            "audio_model_readiness",
            extra={
                "event": "audio_model_readiness",
                **asdict(state),
                "internal_error_type": type(exc).__name__,
            },
        )
        return _safe_readiness_result(
            status="unavailable",
            device=(state.selected_device if state.selected_device != "unknown" else None),
            error_category=state.error_category,
        )


def get_audio_model_readiness() -> Dict[str, Any]:
    with _readiness_check_lock:
        with _readiness_state_lock:
            cached = (
                _AudioReadinessState(**asdict(_last_readiness_state))
                if _last_readiness_state
                else None
            )
        if cached and cached.error_category is None and all(
            (
                cached.model_files_present,
                cached.pinned_revision_verified,
                cached.config_mapping_valid,
                cached.feature_extractor_valid,
                cached.decoder_available,
                cached.selected_device in {"cpu", "cuda"},
                cached.warmup_status in {"disabled", "successful"},
            )
        ):
            try:
                _resolve_decoder()
            except Exception:
                cached.decoder_available = False
                cached.error_category = "decoder_unavailable"
                _store_readiness_state(cached)
                logger.error(
                    "audio_model_readiness",
                    extra={
                        "event": "audio_model_readiness",
                        **asdict(cached),
                        "internal_error_type": "decoder_recheck_failed",
                    },
                )
                return _safe_readiness_result(
                    status="unavailable",
                    device=cached.selected_device,
                    error_category="decoder_unavailable",
                )
            return _safe_readiness_result(
                status="ready",
                device=cached.selected_device,
                error_category=None,
            )
        return _evaluate_audio_model_readiness()


def _get_inference_semaphore() -> Tuple[threading.BoundedSemaphore, float]:
    global _inference_semaphore, _inference_semaphore_size
    config = _load_runtime_config()
    if (
        _inference_semaphore is not None
        and _inference_semaphore_size == config.max_concurrent_inferences
    ):
        return _inference_semaphore, config.inference_acquire_timeout_seconds
    with _semaphore_lock:
        if (
            _inference_semaphore is None
            or _inference_semaphore_size != config.max_concurrent_inferences
        ):
            _inference_semaphore = threading.BoundedSemaphore(
                config.max_concurrent_inferences
            )
            _inference_semaphore_size = config.max_concurrent_inferences
        return _inference_semaphore, config.inference_acquire_timeout_seconds


def _capture_bounded_stream(
    stream: Any,
    *,
    limit: int,
    output: List[bytes],
    exceeded: List[bool],
) -> None:
    retained = 0
    try:
        while True:
            block = stream.read(DECODER_READ_BLOCK_BYTES)
            if not block:
                break
            remaining = max(0, limit - retained)
            if remaining:
                output.append(block[:remaining])
                retained += min(len(block), remaining)
            if len(block) > remaining:
                exceeded[0] = True
    finally:
        stream.close()


def _run_decoder(
    command: List[str],
    *,
    max_output_bytes: int,
    timeout_seconds: float,
) -> _DecoderResult:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise AudioModelUnavailableError("The audio decoder executable was not found") from exc
    except OSError as exc:
        raise AudioModelUnavailableError("The audio decoder could not be started") from exc

    if process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise AudioModelUnavailableError("The audio decoder streams could not be opened")

    stdout_blocks: List[bytes] = []
    stderr_blocks: List[bytes] = []
    stdout_exceeded = [False]
    stderr_exceeded = [False]
    stdout_reader = threading.Thread(
        target=_capture_bounded_stream,
        kwargs={
            "stream": process.stdout,
            "limit": max_output_bytes,
            "output": stdout_blocks,
            "exceeded": stdout_exceeded,
        },
        daemon=True,
    )
    stderr_reader = threading.Thread(
        target=_capture_bounded_stream,
        kwargs={
            "stream": process.stderr,
            "limit": DECODER_STDERR_MAX_BYTES,
            "output": stderr_blocks,
            "exceeded": stderr_exceeded,
        },
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()
    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.wait()
        stdout_reader.join()
        stderr_reader.join()
        raise AudioLimitError("Audio decoding exceeded the configured time limit") from exc

    stdout_reader.join()
    stderr_reader.join()
    if stderr_exceeded[0]:
        logger.info("Audio decoder diagnostic output was truncated")
    return _DecoderResult(
        returncode=returncode,
        stdout=b"".join(stdout_blocks),
        stderr=b"".join(stderr_blocks),
        stdout_limit_exceeded=stdout_exceeded[0],
    )


def _raise_decoder_failure(stderr: bytes) -> None:
    diagnostic = stderr.decode("utf-8", errors="replace").lower()
    rejected_input_markers = (
        "invalid data",
        "unsupported",
        "unknown format",
        "could not find codec parameters",
        "matches no streams",
        "does not contain any stream",
        "error opening input",
        "moov atom not found",
    )
    if any(marker in diagnostic for marker in rejected_input_markers):
        raise InvalidAudioError("The uploaded audio is corrupt or unsupported")
    raise AudioModelUnavailableError("The audio decoder failed internally")


def _decode_audio(audio_path: str) -> np.ndarray:
    path = Path(audio_path).resolve()
    if not path.is_file() or path.stat().st_size == 0:
        raise InvalidAudioError("The uploaded audio is empty or missing")
    if path.stat().st_size > _max_source_bytes():
        raise AudioLimitError("The compressed audio exceeds the configured size limit")

    max_seconds = _max_decode_seconds()
    decode_seconds = max_seconds + 1.0
    command = [
        _resolve_decoder(),
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ac",
        "1",
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-t",
        f"{decode_seconds:.3f}",
        "pipe:1",
    ]
    max_output_bytes = math.ceil(decode_seconds * TARGET_SAMPLE_RATE * 4)
    completed = _run_decoder(
        command,
        max_output_bytes=max_output_bytes,
        timeout_seconds=_decoder_timeout_seconds(),
    )
    if completed.stdout_limit_exceeded:
        raise AudioLimitError("Decoded audio exceeded the configured sample limit")
    if completed.returncode != 0:
        logger.info(
            "Audio decoder rejected input (exit=%s)",
            completed.returncode,
        )
        _raise_decoder_failure(completed.stderr)
    if not completed.stdout or len(completed.stdout) % 4:
        raise InvalidAudioError("The uploaded audio did not contain usable samples")

    waveform = np.frombuffer(completed.stdout, dtype="<f4").copy()
    max_samples = math.floor(max_seconds * TARGET_SAMPLE_RATE)
    if waveform.size > max_samples:
        raise AudioLimitError("The audio duration exceeds the configured limit")
    if waveform.size < _minimum_samples():
        raise InvalidAudioError("The audio clip is too short for analysis")
    if not np.isfinite(waveform).all():
        raise InvalidAudioError("The decoded audio contains invalid samples")
    rms = float(np.sqrt(np.mean(np.square(waveform, dtype=np.float64))))
    if not math.isfinite(rms) or rms <= _silence_threshold():
        raise InvalidAudioError("The audio clip is silent or too quiet for analysis")
    return waveform


def _chunk_waveform(waveform: np.ndarray) -> List[Tuple[np.ndarray, int]]:
    chunk_samples, overlap_samples = _chunk_settings()
    minimum_samples = _minimum_samples()
    sample_count = int(waveform.size)
    if sample_count <= chunk_samples:
        return [(waveform, sample_count)]

    step = chunk_samples - overlap_samples
    starts = [0]
    while starts[-1] + chunk_samples < sample_count:
        candidate = starts[-1] + step
        remaining = sample_count - candidate
        if remaining < minimum_samples:
            candidate = sample_count - chunk_samples
        if candidate <= starts[-1]:
            break
        starts.append(candidate)

    ends = [start + chunk_samples for start in starts]
    boundaries = [0]
    for index in range(len(starts) - 1):
        boundaries.append((ends[index] + starts[index + 1]) // 2)
    boundaries.append(sample_count)

    chunks: List[Tuple[np.ndarray, int]] = []
    for index, start in enumerate(starts):
        unique_weight = boundaries[index + 1] - boundaries[index]
        if unique_weight <= 0:
            raise AudioModelUnavailableError("Audio chunk configuration is invalid")
        chunks.append((waveform[start : min(start + chunk_samples, sample_count)], unique_weight))
    return chunks


def _predict_probabilities(
    chunks: Iterable[Tuple[np.ndarray, int]],
    bundle: _ModelBundle,
    *,
    operation: str = "analysis",
) -> Tuple[np.ndarray, int]:
    weighted_probability = np.zeros(2, dtype=np.float64)
    total_weight = 0
    chunk_count = 0
    preprocessing_seconds = 0.0
    inference_seconds = 0.0
    aggregation_seconds = 0.0
    prediction_status = "success"

    try:
        with _predict_lock, bundle.torch.inference_mode():
            for chunk, weight in chunks:
                preprocessing_started = time.perf_counter()
                inputs = bundle.feature_extractor(
                    chunk,
                    sampling_rate=TARGET_SAMPLE_RATE,
                    return_tensors="pt",
                )
                model_inputs = {
                    key: value.to(bundle.device)
                    for key, value in inputs.items()
                    if hasattr(value, "to")
                }
                preprocessing_seconds += time.perf_counter() - preprocessing_started

                inference_started = time.perf_counter()
                logits = bundle.model(**model_inputs).logits
                probabilities = (
                    bundle.torch.softmax(logits, dim=-1)[0]
                    .detach()
                    .cpu()
                    .numpy()
                )
                inference_seconds += time.perf_counter() - inference_started
                if probabilities.shape != (2,) or not np.isfinite(probabilities).all():
                    raise RuntimeError("The audio model returned invalid probabilities")
                weighted_probability += probabilities.astype(np.float64) * weight
                total_weight += weight
                chunk_count += 1

        aggregation_started = time.perf_counter()
        if total_weight <= 0 or chunk_count == 0:
            raise RuntimeError("The audio model did not analyze any chunks")
        aggregate = weighted_probability / total_weight
        if not np.isfinite(aggregate).all() or np.any(aggregate < 0.0):
            raise RuntimeError("The audio model returned invalid aggregate probabilities")
        total = float(aggregate.sum())
        if not math.isfinite(total) or total <= 0:
            raise RuntimeError("The audio model returned an invalid probability total")
        if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
            raise RuntimeError(
                "The audio model probability total exceeded floating-point tolerance"
            )
        if total != 1.0:
            aggregate = aggregate / total
        aggregation_seconds = time.perf_counter() - aggregation_started
        return aggregate, chunk_count
    except Exception:
        prediction_status = "error"
        raise
    finally:
        safe_fields = {
            "chunk_count": chunk_count,
            "device": str(bundle.device).split(":", 1)[0],
        }
        _log_timing(
            "preprocessing",
            preprocessing_seconds,
            status=prediction_status,
            operation=operation,
            **safe_fields,
        )
        _log_timing(
            "chunk_inference",
            inference_seconds,
            status=prediction_status,
            operation=operation,
            **safe_fields,
        )
        _log_timing(
            "aggregation",
            aggregation_seconds,
            status=prediction_status,
            operation=operation,
            **safe_fields,
        )


def analyze_audio(audio_path: str) -> Dict[str, Any]:
    total_started = time.perf_counter()
    request_status = "success"
    semaphore, acquire_timeout = _get_inference_semaphore()
    wait_started = time.perf_counter()
    acquired = semaphore.acquire(timeout=acquire_timeout)
    _log_timing(
        "concurrency_wait",
        time.perf_counter() - wait_started,
        status="success" if acquired else "timeout",
    )
    if not acquired:
        _log_timing(
            "total_request",
            time.perf_counter() - total_started,
            status="busy",
        )
        raise AudioBusyError("Audio inference capacity is busy")

    try:
        decode_started = time.perf_counter()
        decode_status = "success"
        try:
            waveform = _decode_audio(audio_path)
        except Exception:
            decode_status = "error"
            raise
        finally:
            _log_timing(
                "decode",
                time.perf_counter() - decode_started,
                status=decode_status,
            )

        chunks = _chunk_waveform(waveform)
        model_load_started = time.perf_counter()
        model_load_status = "success"
        try:
            bundle = _load_model_bundle()
        except Exception:
            model_load_status = "error"
            raise
        finally:
            _log_timing(
                "model_load",
                time.perf_counter() - model_load_started,
                status=model_load_status,
            )
        probabilities, chunk_count = _predict_probabilities(chunks, bundle)

        fake_probability = float(probabilities[0])
        authentic_probability = float(probabilities[1])
        predicted_class = int(np.argmax(probabilities))
        label = "Suspected Deepfake" if predicted_class == 0 else "Authentic"
        confidence = fake_probability if predicted_class == 0 else authentic_probability
        chunk_phrase = (
            "one bounded chunk"
            if chunk_count == 1
            else f"{chunk_count} bounded chunks"
        )

        return {
            "media_type": "audio",
            "label": label,
            "confidence": round(confidence * 100.0, 2),
            "fake_probability": round(fake_probability * 100.0, 2),
            "authentic_probability": round(authentic_probability * 100.0, 2),
            "explanation": (
                f"The local Wav2Vec2 audio classifier analyzed {chunk_phrase} and "
                "assigned the stronger probability to its "
                f"{('fake' if predicted_class == 0 else 'real')} class. "
                "This model signal is not proof of origin or a specific manipulation method."
            ),
            "heatmap_url": None,
            "xai_overlay_url": None,
            "xai_panel_url": None,
            "xai_method": None,
            "xai_target_class": None,
            "xai_predicted_class": None,
            "xai_layer": None,
            "xai_map_strength": None,
            "xai_error": None,
            "model_version": MODEL_VERSION,
        }
    except Exception:
        request_status = "error"
        raise
    finally:
        semaphore.release()
        _log_timing(
            "total_request",
            time.perf_counter() - total_started,
            status=request_status,
        )
