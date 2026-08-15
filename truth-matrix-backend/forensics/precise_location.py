from __future__ import annotations

import base64
import json
import math
import os
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENCRYPTION_VERSION = "aes-256-gcm-v1"
_ENVELOPE_VERSION = 1
_MAX_SOURCE_LENGTH = 96
_MAX_OBSERVATIONS = 64
_ISO6709_PATTERN = re.compile(
    r"^\s*([+-]\d{1,2}(?:\.\d+)?)([+-]\d{1,3}(?:\.\d+)?)(?:([+-]\d+(?:\.\d+)?))?/?\s*$"
)


@dataclass(frozen=True)
class PreciseLocation:
    """Validated, bounded coordinates retained only in the private pipeline."""

    latitude: float
    longitude: float
    altitude_meters: Optional[float] = None
    source: str = "Embedded media metadata"
    accuracy_meters: Optional[float] = None

    def to_payload(self) -> dict[str, Any]:
        """Return the strict private JSON payload used for encryption."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_meters": self.altitude_meters,
            "source": self.source[:_MAX_SOURCE_LENGTH],
            "accuracy_meters": self.accuracy_meters,
        }


def precise_location_enabled() -> bool:
    """Return whether private coordinate persistence is explicitly enabled."""
    raw = os.getenv("LOCATION_PRECISE_ENABLED", "false").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("LOCATION_PRECISE_ENABLED must be true or false")


def coordinate_decimal_places() -> int:
    """Return the validated coordinate precision used in owner responses."""
    try:
        value = int(os.getenv("LOCATION_COORDINATE_DECIMAL_PLACES", "6"))
    except ValueError as exc:
        raise RuntimeError("LOCATION_COORDINATE_DECIMAL_PLACES must be an integer") from exc
    if not 3 <= value <= 8:
        raise RuntimeError("LOCATION_COORDINATE_DECIMAL_PLACES must be between 3 and 8")
    return value


def _number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, Fraction):
            parsed = float(value)
        elif hasattr(value, "numerator") and hasattr(value, "denominator"):
            parsed = float(value.numerator) / float(value.denominator)
        elif isinstance(value, str) and "/" in value:
            parsed = float(Fraction(value.strip()))
        else:
            parsed = float(value)
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def _coordinate(value: Any, reference: Any, maximum: float) -> Optional[float]:
    components: Sequence[Any]
    if isinstance(value, (list, tuple)):
        components = value
    else:
        text = str(value).strip()
        dms = re.findall(r"[+-]?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?", text)
        components = dms if len(dms) >= 3 else [value]

    if len(components) >= 3:
        degrees, minutes, seconds = (_number(item) for item in components[:3])
        if degrees is None or minutes is None or seconds is None:
            return None
        if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
            return None
        sign = -1.0 if degrees < 0 else 1.0
        parsed = sign * (abs(degrees) + minutes / 60.0 + seconds / 3600.0)
    else:
        parsed = _number(components[0]) if components else None
        if parsed is None:
            return None

    direction = str(reference or "").strip().upper()
    if direction in {"S", "W"}:
        parsed = -abs(parsed)
    elif direction in {"N", "E"}:
        parsed = abs(parsed)
    elif direction:
        return None
    if not -maximum <= parsed <= maximum:
        return None
    return parsed


def _leaf(key: object) -> str:
    return "".join(character for character in str(key).lower() if character.isalnum())


def _values(observations: Iterable[Tuple[str, Any]]) -> dict[str, tuple[str, Any]]:
    output: dict[str, tuple[str, Any]] = {}
    for source_tag, value in list(observations)[:_MAX_OBSERVATIONS]:
        leaf = _leaf(source_tag.rsplit(".", 1)[-1].rsplit(":", 1)[-1])
        output.setdefault(leaf, (str(source_tag)[:256], value))
    return output


def extract_precise_location(
    observations: Iterable[Tuple[str, Any]],
    *,
    detected_mime_type: str,
) -> Optional[PreciseLocation]:
    """Parse valid EXIF/XMP/container coordinates from bounded observations."""
    values = _values(observations)
    latitude_item = values.get("gpslatitude") or values.get("latitude")
    longitude_item = values.get("gpslongitude") or values.get("longitude")

    if latitude_item and longitude_item:
        latitude = _coordinate(
            latitude_item[1],
            (values.get("gpslatituderef") or values.get("latituderef") or ("", None))[1],
            90.0,
        )
        longitude = _coordinate(
            longitude_item[1],
            (values.get("gpslongituderef") or values.get("longituderef") or ("", None))[1],
            180.0,
        )
        if latitude is not None and longitude is not None:
            altitude = _number((values.get("gpsaltitude") or values.get("altitude") or ("", None))[1])
            altitude_ref = _number((values.get("gpsaltituderef") or ("", None))[1])
            if altitude is not None and altitude_ref == 1:
                altitude = -abs(altitude)
            source = "Embedded image metadata" if detected_mime_type.startswith("image/") else "Embedded media metadata"
            return PreciseLocation(latitude, longitude, altitude, source)

    coordinate_pair = values.get("gpscoordinates") or values.get("coordinates")
    if coordinate_pair:
        components = re.findall(r"[+-]?\d+(?:\.\d+)?", str(coordinate_pair[1]))
        if len(components) >= 2:
            latitude = _coordinate(components[0], None, 90.0)
            longitude = _coordinate(components[1], None, 180.0)
            if latitude is not None and longitude is not None:
                return PreciseLocation(latitude, longitude, None, "Embedded media metadata")

    for key in ("location", "iso6709", "locationiso6709", "comapplequicktimelocationiso6709"):
        item = values.get(key)
        if not item or not isinstance(item[1], str):
            continue
        match = _ISO6709_PATTERN.match(item[1])
        if not match:
            continue
        latitude = _coordinate(match.group(1), None, 90.0)
        longitude = _coordinate(match.group(2), None, 180.0)
        altitude = _number(match.group(3))
        if latitude is not None and longitude is not None:
            return PreciseLocation(latitude, longitude, altitude, "Embedded container metadata")
    return None


def _encryption_key() -> bytes:
    raw = os.getenv("LOCATION_ENCRYPTION_KEY", "").strip()
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("LOCATION_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(key) != 32:
        raise RuntimeError("LOCATION_ENCRYPTION_KEY must decode to exactly 32 bytes")
    return key


def encrypt_location(location: PreciseLocation, *, analysis_id: str, user_id: str) -> str:
    """Encrypt coordinates with AES-256-GCM bound to analysis and owner IDs."""
    key = _encryption_key()
    nonce = os.urandom(12)
    plaintext = json.dumps(location.to_payload(), separators=(",", ":"), sort_keys=True).encode("utf-8")
    aad = f"truth-matrix-location:{analysis_id}:{user_id}:{ENCRYPTION_VERSION}".encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    envelope = {
        "v": _ENVELOPE_VERSION,
        "n": base64.urlsafe_b64encode(nonce).decode("ascii").rstrip("="),
        "c": base64.urlsafe_b64encode(ciphertext).decode("ascii").rstrip("="),
    }
    return base64.urlsafe_b64encode(json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")).decode("ascii")


def decrypt_location(encrypted_payload: str, *, analysis_id: str, user_id: str) -> PreciseLocation:
    """Authenticate and decrypt one owner-scoped coordinate payload."""
    try:
        envelope = json.loads(base64.urlsafe_b64decode(encrypted_payload).decode("utf-8"))
        nonce_text = envelope["n"]
        cipher_text = envelope["c"]
        nonce = base64.urlsafe_b64decode(nonce_text + "=" * (-len(nonce_text) % 4))
        ciphertext = base64.urlsafe_b64decode(cipher_text + "=" * (-len(cipher_text) % 4))
        aad = f"truth-matrix-location:{analysis_id}:{user_id}:{ENCRYPTION_VERSION}".encode("utf-8")
        plaintext = AESGCM(_encryption_key()).decrypt(nonce, ciphertext, aad)
        data = json.loads(plaintext.decode("utf-8"))
        latitude = _coordinate(data.get("latitude"), None, 90.0)
        longitude = _coordinate(data.get("longitude"), None, 180.0)
        if latitude is None or longitude is None:
            raise ValueError("Invalid coordinate payload")
        return PreciseLocation(
            latitude=latitude,
            longitude=longitude,
            altitude_meters=_number(data.get("altitude_meters")),
            source=str(data.get("source") or "Embedded media metadata")[:_MAX_SOURCE_LENGTH],
            accuracy_meters=_number(data.get("accuracy_meters")),
        )
    except Exception as exc:
        raise ValueError("Stored precise location could not be decrypted") from exc
