from __future__ import annotations

import importlib
import multiprocessing
import json
import os
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from time import perf_counter
from types import ModuleType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from forensics.c2pa_provenance import classify_c2pa_provenance
from forensics.hashing import normalize_mime_type, resolve_workspace_file
from schemas.forensic_schema import (
    C2paAction,
    C2paEvidence,
    C2paValidationStatus,
)


PathLike = Union[str, Path]

DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
DEFAULT_REPORT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_RAW_MAX_BYTES = 32 * 1024
DEFAULT_TRUST_MAX_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20
MAX_REPORT_MAX_BYTES = 16 * 1024 * 1024
MAX_RAW_MAX_BYTES = 256 * 1024
MAX_TRUST_MAX_BYTES = 8 * 1024 * 1024
MAX_ASSERTION_LABELS = 128
MAX_ACTIONS = 64
MAX_VALIDATION_STATUSES = 128
MAX_TEXT_CHARS = 512

SUPPORTED_C2PA_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/x-msvideo",
        "audio/wav",
        "audio/mpeg",
        "audio/mp4",
    }
)

_URL_RE = re.compile(r"(?i)\bhttps?://[^\s\]\[<>{}\"']+")
_WINDOWS_PATH_RE = re.compile(r"(?i)\b[a-z]:\\[^\s]+")
_POSIX_PRIVATE_PATH_RE = re.compile(r"(?i)(?:/home/|/users/|/tmp/)[^\s]+")
_PEM_RE = re.compile(
    r"-----BEGIN [^-]+-----.*?-----END [^-]+-----",
    flags=re.DOTALL,
)
_SAFE_CODE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


class C2paExtractionResult(BaseModel):
    """Structured independent C2PA result plus elapsed processing time."""

    model_config = ConfigDict(extra="forbid")

    evidence: C2paEvidence
    processing_time_ms: int = Field(..., ge=0)


class _C2paReadFailure(RuntimeError):
    """Internal safe error category that never includes SDK detail."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _configured_int(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _safe_text(value: Any, *, maximum: int = MAX_TEXT_CHARS) -> Optional[str]:
    if not isinstance(value, (str, int, float, bool)):
        return None
    text = str(value).replace("\x00", " ")
    text = " ".join(text.split())
    text = _PEM_RE.sub("[certificate omitted]", text)
    text = _URL_RE.sub("[remote reference]", text)
    text = _WINDOWS_PATH_RE.sub("[local path]", text)
    text = _POSIX_PRIVATE_PATH_RE.sub("[local path]", text)
    if not text:
        return None
    return text[:maximum]


def _safe_identifier(value: Any) -> Optional[str]:
    text = _safe_text(value, maximum=256)
    if text == "[remote reference]":
        return "[remote manifest identifier]"
    return text


def _safe_code(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    code = _SAFE_CODE_RE.sub("", value.strip())[:128]
    return code or None


def _safe_digital_source_type(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.replace("\x00", " ").split())[:512]
    if cleaned.startswith(
        (
            "http://cv.iptc.org/newscodes/digitalsourcetype/",
            "https://cv.iptc.org/newscodes/digitalsourcetype/",
        )
    ):
        return cleaned
    return _safe_text(cleaned)


def _load_c2pa_sdk() -> ModuleType:
    """Load the optional native C2PA SDK without global settings mutation."""
    return importlib.import_module("c2pa")


def _read_bounded_trust_anchors(maximum_bytes: int) -> Optional[str]:
    configured = os.getenv("C2PA_TRUST_ANCHORS_PATH", "").strip()
    if not configured:
        return None
    trust_path = Path(configured).expanduser().resolve(strict=True)
    if not trust_path.is_file():
        raise ValueError("Configured C2PA trust anchors must be a regular file.")
    if trust_path.stat().st_size > maximum_bytes:
        raise ValueError("Configured C2PA trust anchors exceed the byte limit.")
    with trust_path.open("rb") as source:
        content = source.read(maximum_bytes + 1)
    if len(content) > maximum_bytes:
        raise ValueError("Configured C2PA trust anchors exceed the byte limit.")
    try:
        anchors = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Configured C2PA trust anchors are not UTF-8 PEM.") from exc
    if "-----BEGIN CERTIFICATE-----" not in anchors:
        raise ValueError("Configured C2PA trust anchors do not contain a PEM certificate.")
    return anchors


def _build_settings(trust_anchors: Optional[str]) -> Dict[str, Any]:
    settings: Dict[str, Any] = {
        "version": 1,
        "core": {"allowed_network_hosts": []},
        "verify": {
            "verify_after_reading": True,
            "verify_trust": True,
            "verify_timestamp_trust": True,
            "remote_manifest_fetch": False,
            "ocsp_fetch": False,
        },
    }
    if trust_anchors:
        # User anchors extend, rather than replace, the SDK's built-in anchors.
        settings["trust"] = {"user_anchors": trust_anchors}
    return settings


def _reader_remote_reference(reader: Any) -> bool:
    remote_reference = False
    try:
        get_remote_url = getattr(reader, "get_remote_url", None)
        if callable(get_remote_url) and get_remote_url():
            remote_reference = True
    except Exception:
        pass
    try:
        is_embedded = getattr(reader, "is_embedded", None)
        if callable(is_embedded) and is_embedded() is False:
            remote_reference = True
    except Exception:
        pass
    return remote_reference


def _read_report(
    sdk: ModuleType,
    path: Path,
    detected_mime_type: str,
    settings_dict: Mapping[str, Any],
    report_max_bytes: int,
) -> Tuple[Mapping[str, Any], bool]:
    settings_factory = getattr(sdk, "Settings")
    context_factory = getattr(sdk, "Context")
    reader_factory = getattr(sdk, "Reader")

    with settings_factory.from_dict(dict(settings_dict)) as settings:
        with context_factory(settings) as context:
            with path.open("rb") as stream:
                with reader_factory(
                    detected_mime_type,
                    stream,
                    context=context,
                ) as reader:
                    remote_reference = _reader_remote_reference(reader)
                    report_json = reader.json()

    if not isinstance(report_json, str):
        raise ValueError("C2PA Reader returned a non-text report.")
    if len(report_json) > report_max_bytes:
        raise OverflowError("C2PA Reader report exceeds the byte limit.")
    encoded = report_json.encode("utf-8")
    if len(encoded) > report_max_bytes:
        raise OverflowError("C2PA Reader report exceeds the byte limit.")
    parsed = json.loads(encoded)
    if not isinstance(parsed, dict):
        raise ValueError("C2PA Reader report is not a JSON object.")
    return parsed, remote_reference


def _reader_worker(
    send_connection: Any,
    path: str,
    detected_mime_type: str,
    settings_dict: Dict[str, Any],
    report_max_bytes: int,
) -> None:
    """Run the native SDK in a killable child process with silent output."""
    try:
        with open(os.devnull, "w", encoding="utf-8") as sink:
            with redirect_stdout(sink), redirect_stderr(sink):
                sdk = _load_c2pa_sdk()
                report, remote_reference = _read_report(
                    sdk,
                    Path(path),
                    detected_mime_type,
                    settings_dict,
                    report_max_bytes,
                )
        send_connection.send(("ok", report, remote_reference))
    except BaseException as exc:
        if _is_manifest_not_found(exc):
            code = "manifest_not_found"
        elif _is_unsupported_error(exc):
            code = "unsupported"
        elif isinstance(exc, OverflowError):
            code = "report_too_large"
        elif isinstance(exc, (json.JSONDecodeError, UnicodeError, ValueError)):
            code = "malformed"
        elif _looks_like_resource_error(exc):
            code = "resource"
        else:
            code = "sdk_error"
        try:
            send_connection.send((code, None, code == "resource"))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        send_connection.close()


def _read_report_with_timeout(
    sdk: ModuleType,
    path: Path,
    detected_mime_type: str,
    settings_dict: Mapping[str, Any],
    report_max_bytes: int,
    timeout_seconds: int,
) -> Tuple[Mapping[str, Any], bool]:
    # Test doubles remain in-process; the installed native module is isolated
    # so a malformed asset cannot indefinitely occupy the API worker.
    if getattr(sdk, "__name__", None) != "c2pa":
        return _read_report(
            sdk,
            path,
            detected_mime_type,
            settings_dict,
            report_max_bytes,
        )

    process_context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = process_context.Pipe(duplex=False)
    process = process_context.Process(
        target=_reader_worker,
        args=(
            send_connection,
            str(path),
            detected_mime_type,
            dict(settings_dict),
            report_max_bytes,
        ),
        name="truth-matrix-c2pa-reader",
    )
    process.daemon = True
    try:
        process.start()
        send_connection.close()
        if not receive_connection.poll(timeout_seconds):
            process.terminate()
            process.join(timeout=2)
            raise TimeoutError("C2PA Reader exceeded its execution-time limit.")
        try:
            code, report, remote_reference = receive_connection.recv()
        except (EOFError, OSError) as exc:
            raise _C2paReadFailure("sdk_error") from exc
        process.join(timeout=2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        if code != "ok" or not isinstance(report, Mapping):
            raise _C2paReadFailure(str(code))
        return report, bool(remote_reference)
    finally:
        send_connection.close()
        receive_connection.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)


def _is_manifest_not_found(error: BaseException) -> bool:
    if isinstance(error, _C2paReadFailure):
        return error.code == "manifest_not_found"
    name = type(error).__name__.lower()
    message = str(error).lstrip().lower()
    return "manifestnotfound" in name or message.startswith("manifestnotfound:")


def _is_unsupported_error(error: BaseException) -> bool:
    if isinstance(error, _C2paReadFailure):
        return error.code == "unsupported"
    name = type(error).__name__.lower()
    message = str(error).lstrip().lower()
    return "notsupported" in name or message.startswith("notsupported:")


def _looks_like_resource_error(error: BaseException) -> bool:
    if isinstance(error, _C2paReadFailure):
        return error.code == "resource"
    message = str(error).lower()
    return "remote" in message or "resource" in message or "http" in message


def _contains_remote_reference(value: Any, *, key: str = "", depth: int = 0) -> bool:
    if depth > 8:
        return False
    if isinstance(value, Mapping):
        for child_key, child_value in list(value.items())[:512]:
            if _contains_remote_reference(
                child_value,
                key=str(child_key),
                depth=depth + 1,
            ):
                return True
        return False
    if isinstance(value, list):
        return any(
            _contains_remote_reference(item, key=key, depth=depth + 1)
            for item in value[:512]
        )
    if not isinstance(value, str) or not value.lower().startswith(("http://", "https://")):
        return False
    normalized_key = key.lower().replace("_", "")
    if normalized_key in {"digitalsourcetype", "validationurl"}:
        return False
    if normalized_key == "activemanifest":
        return True
    return any(
        marker in normalized_key
        for marker in ("remote", "resource", "thumbnail", "icon", "url", "uri", "identifier")
    )


def _extract_active_manifest(
    report: Mapping[str, Any],
) -> Tuple[str, Mapping[str, Any]]:
    active_identifier = report.get("active_manifest")
    manifests = report.get("manifests")
    if not isinstance(active_identifier, str) or not isinstance(manifests, Mapping):
        raise ValueError("C2PA report has no active manifest mapping.")
    active = manifests.get(active_identifier)
    if not isinstance(active, Mapping):
        raise ValueError("C2PA active manifest is missing from the manifest mapping.")
    return active_identifier, active


def _extract_claim_generator(active: Mapping[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    generator = _safe_text(active.get("claim_generator"), maximum=256)
    version: Optional[str] = None
    generator_info = active.get("claim_generator_info")
    if isinstance(generator_info, list):
        for item in generator_info[:16]:
            if not isinstance(item, Mapping):
                continue
            name = _safe_text(item.get("name"), maximum=128)
            candidate_version = _safe_text(item.get("version"), maximum=64)
            if generator is None and name:
                generator = name
            if candidate_version:
                version = candidate_version
                break
    if version is None and generator and " " not in generator and "/" in generator:
        candidate = generator.rsplit("/", 1)[-1]
        if candidate and len(candidate) <= 64:
            version = candidate
    return generator, version


def _extract_assertions(
    active: Mapping[str, Any],
) -> Tuple[List[str], List[C2paAction]]:
    labels: List[str] = []
    actions: List[C2paAction] = []
    seen_actions: set[tuple[str, Optional[str], Optional[str], Optional[str]]] = set()
    assertions = active.get("assertions")
    if not isinstance(assertions, list):
        return labels, actions

    for assertion in assertions[:MAX_ASSERTION_LABELS]:
        if not isinstance(assertion, Mapping):
            continue
        label = _safe_text(assertion.get("label"), maximum=256)
        if label and label not in labels:
            labels.append(label)
        data = assertion.get("data")
        if not isinstance(data, Mapping):
            continue
        raw_actions = data.get("actions")
        if not isinstance(raw_actions, list):
            continue
        for raw_action in raw_actions:
            if len(actions) >= MAX_ACTIONS or not isinstance(raw_action, Mapping):
                break
            action = _safe_text(raw_action.get("action"), maximum=128)
            if not action:
                continue
            digital_source = _safe_digital_source_type(
                raw_action.get("digitalSourceType", raw_action.get("digital_source_type"))
            )
            software_agent_value = raw_action.get(
                "softwareAgent", raw_action.get("software_agent")
            )
            if isinstance(software_agent_value, Mapping):
                software_agent_value = software_agent_value.get("name")
            software_agent = _safe_text(software_agent_value, maximum=256)
            description = _safe_text(raw_action.get("description"), maximum=512)
            action_key = (action, digital_source, software_agent, description)
            if action_key in seen_actions:
                continue
            seen_actions.add(action_key)
            actions.append(
                C2paAction(
                    action=action,
                    digital_source_type=digital_source,
                    software_agent=software_agent,
                    description=description,
                    # Manifest action parameters may contain private resource
                    # identifiers, so the normal evidence contract omits them.
                    parameters={},
                )
            )
    return labels, actions


def _validation_category(key: str, inherited: str) -> str:
    normalized = key.lower()
    if normalized == "success":
        return "success"
    if normalized in {"informational", "info"}:
        return "informational"
    if normalized in {"failure", "failures", "validation_status"}:
        return "failure"
    return inherited


def _walk_validation_statuses(
    value: Any,
    *,
    category: str,
) -> Iterable[C2paValidationStatus]:
    if isinstance(value, Mapping):
        code = _safe_code(value.get("code"))
        if code:
            summary = _safe_text(value.get("explanation"), maximum=384)
            yield C2paValidationStatus(
                code=code,
                summary=summary or code,
                category=category,
            )
            return
        for key, child in value.items():
            yield from _walk_validation_statuses(
                child,
                category=_validation_category(str(key), category),
            )
    elif isinstance(value, list):
        for child in value:
            yield from _walk_validation_statuses(child, category=category)


def _extract_validation_statuses(
    report: Mapping[str, Any],
) -> Tuple[List[C2paValidationStatus], bool]:
    statuses: List[C2paValidationStatus] = []
    seen: set[Tuple[str, str, str]] = set()
    truncated = False
    sources = (
        (report.get("validation_status"), "failure"),
        (report.get("validation_results"), "informational"),
    )
    for source, category in sources:
        for item in _walk_validation_statuses(source, category=category):
            key = (item.code, item.summary, item.category.value)
            if key in seen:
                continue
            if len(statuses) >= MAX_VALIDATION_STATUSES:
                truncated = True
                continue
            seen.add(key)
            statuses.append(item)
    return statuses, truncated


def _classify_states(
    report: Mapping[str, Any],
    statuses: List[C2paValidationStatus],
) -> Tuple[str, str, str]:
    report_state = str(report.get("validation_state", "")).strip().lower()
    failures = [item for item in statuses if item.category.value == "failure"]
    successes = [item for item in statuses if item.category.value == "success"]

    signature_failures = [
        item for item in failures if item.code.lower().startswith("claimsignature.")
    ]
    signature_success = any(
        item.code.lower() == "claimsignature.validated" for item in successes
    )
    if signature_failures:
        signature_state = "invalid"
    elif signature_success or report_state in {"valid", "trusted"}:
        signature_state = "valid"
    else:
        # Reader verifies after reading. A parsed manifest with only data-hash
        # failures can still have a correctly signed claim.
        signature_state = "valid"

    trust_failures = [
        item for item in failures if item.code.lower().startswith("signingcredential.")
    ]
    trust_success = any(
        item.code.lower() == "signingcredential.trusted" for item in successes
    )
    if trust_failures:
        trust_state = "untrusted"
    elif trust_success or report_state == "trusted":
        trust_state = "trusted"
    else:
        trust_state = "unknown"

    hard_failures = [
        item
        for item in failures
        if not item.code.lower().startswith("signingcredential.")
        and item.code.lower() not in {"timestamp.untrusted"}
    ]
    if hard_failures or report_state == "invalid":
        validation_state = "invalid"
    elif report_state in {"valid", "trusted"} or not failures:
        validation_state = "valid"
    else:
        validation_state = "unknown"
    return validation_state, signature_state, trust_state


def _bounded_raw_summary(
    *,
    active_manifest: Optional[str],
    claim_generator: Optional[str],
    claim_generator_version: Optional[str],
    assertion_labels: List[str],
    actions: List[C2paAction],
    ingredient_count: int,
    validation_statuses: List[C2paValidationStatus],
    remote_references_present: bool,
    maximum_bytes: int,
) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "active_manifest": active_manifest,
        "claim_generator": claim_generator,
        "claim_generator_version": claim_generator_version,
        "assertion_labels": assertion_labels,
        "actions": [item.model_dump(mode="json") for item in actions],
        "ingredient_count": ingredient_count,
        "validation_statuses": [
            item.model_dump(mode="json") for item in validation_statuses
        ],
        "remote_references_present": remote_references_present,
    }
    encoded = json.dumps(summary, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) <= maximum_bytes:
        return summary
    return {
        "active_manifest": active_manifest,
        "claim_generator": claim_generator,
        "claim_generator_version": claim_generator_version,
        "assertion_count": len(assertion_labels),
        "action_count": len(actions),
        "ingredient_count": ingredient_count,
        "validation_status_count": len(validation_statuses),
        "remote_references_present": remote_references_present,
        "truncated": True,
    }


def _result(
    started_at: float,
    *,
    status: str,
    manifest_present: bool,
    validation_state: str,
    signature_state: str,
    trust_state: str,
    warnings: Optional[List[str]] = None,
    **details: Any,
) -> C2paExtractionResult:
    evidence = C2paEvidence(
        status=status,
        manifest_present=manifest_present,
        validation_state=validation_state,
        signature_state=signature_state,
        trust_state=trust_state,
        warnings=warnings or [],
        **details,
    )
    evidence = evidence.model_copy(
        update={"provenance": classify_c2pa_provenance(evidence)}
    )
    return C2paExtractionResult(
        evidence=evidence,
        processing_time_ms=_elapsed_ms(started_at),
    )


def verify_c2pa(
    file_path: PathLike,
    *,
    detected_mime_type: Optional[str],
    allowed_root: Optional[PathLike] = None,
) -> C2paExtractionResult:
    """Read and verify local C2PA evidence without network resource fetching.

    Missing credentials are returned as the neutral ``not_present`` status.
    SDK loading, parsing, and validation failures remain isolated from all other
    forensic extractors and from ML inference.
    """

    started_at = perf_counter()
    try:
        path = resolve_workspace_file(file_path, allowed_root)
        normalized_mime = normalize_mime_type(detected_mime_type)
        if normalized_mime not in SUPPORTED_C2PA_MIME_TYPES:
            return _result(
                started_at,
                status="unsupported",
                manifest_present=False,
                validation_state="not_applicable",
                signature_state="not_applicable",
                trust_state="not_applicable",
                warnings=["C2PA verification does not support this detected media type."],
            )

        max_file_bytes = _configured_int(
            "FORENSIC_C2PA_MAX_FILE_BYTES",
            DEFAULT_MAX_FILE_BYTES,
            minimum=1024,
            maximum=4 * 1024 * 1024 * 1024,
        )
        if path.stat().st_size > max_file_bytes:
            return _result(
                started_at,
                status="unavailable",
                manifest_present=False,
                validation_state="unknown",
                signature_state="unknown",
                trust_state="not_checked",
                warnings=["C2PA verification was skipped because the file exceeds its byte limit."],
            )
        report_max_bytes = _configured_int(
            "FORENSIC_C2PA_REPORT_MAX_BYTES",
            DEFAULT_REPORT_MAX_BYTES,
            minimum=4096,
            maximum=MAX_REPORT_MAX_BYTES,
        )
        raw_max_bytes = _configured_int(
            "FORENSIC_C2PA_RAW_MAX_BYTES",
            DEFAULT_RAW_MAX_BYTES,
            minimum=1024,
            maximum=MAX_RAW_MAX_BYTES,
        )
        trust_max_bytes = _configured_int(
            "FORENSIC_C2PA_TRUST_MAX_BYTES",
            DEFAULT_TRUST_MAX_BYTES,
            minimum=1024,
            maximum=MAX_TRUST_MAX_BYTES,
        )
        timeout_seconds = _configured_int(
            "FORENSIC_C2PA_TIMEOUT_SECONDS",
            DEFAULT_TIMEOUT_SECONDS,
            minimum=1,
            maximum=120,
        )
        trust_anchors = _read_bounded_trust_anchors(trust_max_bytes)
        settings_dict = _build_settings(trust_anchors)
    except (FileNotFoundError, PermissionError, OSError, ValueError):
        return _result(
            started_at,
            status="error",
            manifest_present=False,
            validation_state="unknown",
            signature_state="unknown",
            trust_state="not_checked",
            warnings=["C2PA verification configuration or input validation failed."],
        )

    try:
        sdk = _load_c2pa_sdk()
        if not all(hasattr(sdk, name) for name in ("Reader", "Settings", "Context")):
            raise ImportError("C2PA SDK is missing required current APIs.")
    except (ImportError, OSError):
        return _result(
            started_at,
            status="unavailable",
            manifest_present=False,
            validation_state="unknown",
            signature_state="unknown",
            trust_state="not_checked",
            warnings=["The local C2PA SDK could not be loaded; other analysis remains available."],
        )

    try:
        report, reader_remote_reference = _read_report_with_timeout(
            sdk,
            path,
            normalized_mime,
            settings_dict,
            report_max_bytes,
            timeout_seconds,
        )
    except Exception as exc:
        if _is_manifest_not_found(exc):
            return _result(
                started_at,
                status="not_present",
                manifest_present=False,
                validation_state="not_applicable",
                signature_state="not_applicable",
                trust_state="not_applicable",
                warnings=[],
            )
        if _is_unsupported_error(exc):
            return _result(
                started_at,
                status="unsupported",
                manifest_present=False,
                validation_state="not_applicable",
                signature_state="not_applicable",
                trust_state="not_applicable",
                warnings=["The C2PA SDK does not support this media container."],
            )
        if isinstance(exc, TimeoutError):
            warning = "C2PA verification exceeded its configured execution-time limit."
        elif isinstance(exc, OverflowError) or (
            isinstance(exc, _C2paReadFailure) and exc.code == "report_too_large"
        ):
            warning = "The C2PA report exceeded its configured byte limit."
        elif isinstance(exc, (json.JSONDecodeError, UnicodeError, ValueError)) or (
            isinstance(exc, _C2paReadFailure) and exc.code == "malformed"
        ):
            warning = "The C2PA SDK returned a malformed or unusable manifest report."
        elif _looks_like_resource_error(exc):
            warning = "A C2PA manifest or resource reference could not be resolved; remote fetching remains disabled."
        else:
            warning = "C2PA manifest parsing or verification failed within the isolated extractor."
        return _result(
            started_at,
            status="error",
            manifest_present=False,
            validation_state="unknown",
            signature_state="unknown",
            trust_state="unknown",
            remote_references_present=_looks_like_resource_error(exc),
            remote_fetch_performed=False,
            warnings=[warning],
        )

    manifests = report.get("manifests")
    if not report.get("active_manifest") and not manifests:
        return _result(
            started_at,
            status="not_present",
            manifest_present=False,
            validation_state="not_applicable",
            signature_state="not_applicable",
            trust_state="not_applicable",
            warnings=[],
        )

    try:
        active_identifier_raw, active = _extract_active_manifest(report)
        active_identifier = _safe_identifier(active_identifier_raw)
        claim_generator, claim_generator_version = _extract_claim_generator(active)
        assertion_labels, actions = _extract_assertions(active)
        ingredients = active.get("ingredients")
        ingredient_count = len(ingredients) if isinstance(ingredients, list) else 0
        statuses, statuses_truncated = _extract_validation_statuses(report)
        validation_state, signature_state, trust_state = _classify_states(
            report,
            statuses,
        )
        signature_info = active.get("signature_info")
        if not isinstance(signature_info, Mapping):
            signature_info = {}
        signer = _safe_text(signature_info.get("common_name"), maximum=256)
        issuer = _safe_text(signature_info.get("issuer"), maximum=256)
        remote_references_present = (
            reader_remote_reference
            or _contains_remote_reference(report)
            or _contains_remote_reference(active_identifier_raw, key="active_manifest")
        )
        raw_summary = _bounded_raw_summary(
            active_manifest=active_identifier,
            claim_generator=claim_generator,
            claim_generator_version=claim_generator_version,
            assertion_labels=assertion_labels,
            actions=actions,
            ingredient_count=ingredient_count,
            validation_statuses=statuses,
            remote_references_present=remote_references_present,
            maximum_bytes=raw_max_bytes,
        )
    except (TypeError, ValueError):
        return _result(
            started_at,
            status="error",
            manifest_present=True,
            validation_state="unknown",
            signature_state="unknown",
            trust_state="unknown",
            warnings=["The C2PA manifest report did not contain a usable active manifest."],
        )

    warnings: List[str] = []
    if validation_state == "invalid":
        warnings.append(
            "C2PA validation reported an asset-integrity or manifest-validation failure."
        )
    if signature_state == "valid" and trust_state == "untrusted":
        warnings.append(
            "The C2PA claim signature is valid, but its signer is not anchored in the configured trust lists."
        )
    if remote_references_present:
        warnings.append("Remote C2PA references were detected but were not fetched.")
    if statuses_truncated:
        warnings.append("C2PA validation statuses were truncated to the configured item limit.")

    validation_errors = [
        item.summary for item in statuses if item.category.value == "failure"
    ]
    return _result(
        started_at,
        status="available",
        manifest_present=True,
        active_manifest=active_identifier,
        validation_state=validation_state,
        signature_state=signature_state,
        trust_state=trust_state,
        signer=signer,
        issuer=issuer,
        claim_generator=claim_generator,
        claim_generator_version=claim_generator_version,
        assertion_labels=assertion_labels,
        actions=actions,
        ingredient_count=ingredient_count,
        validation_statuses=statuses,
        validation_errors=validation_errors,
        remote_references_present=remote_references_present,
        remote_fetch_performed=False,
        raw_manifest=raw_summary,
        warnings=warnings,
    )
