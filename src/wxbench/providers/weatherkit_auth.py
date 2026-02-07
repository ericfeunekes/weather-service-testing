"""JWT signing helpers for WeatherKit REST API."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

__all__ = ["build_weatherkit_token"]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _encode_segment(payload: dict[str, object]) -> str:
    content = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url(content)


def _load_private_key(path: str | Path) -> EllipticCurvePrivateKey:
    key_bytes = Path(path).read_bytes()
    private_key = serialization.load_pem_private_key(key_bytes, password=None)
    if not isinstance(private_key, EllipticCurvePrivateKey):
        raise ValueError("WeatherKit private key must be an EC key")
    return private_key


def _sign_es256(private_key: EllipticCurvePrivateKey, message: bytes) -> str:
    signature_der = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(signature_der)
    signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return _b64url(signature)


def build_weatherkit_token(
    *,
    team_id: str,
    service_id: str,
    key_id: str,
    key_path: str | Path,
    now: datetime | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Build a signed WeatherKit JWT for REST API requests."""

    if not team_id or not service_id or not key_id:
        raise ValueError("WeatherKit token requires team_id, service_id, and key_id")

    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)

    iat = int(issued_at.timestamp())
    exp = iat + ttl_seconds

    header = {"alg": "ES256", "kid": key_id, "id": f"{team_id}.{service_id}"}
    payload = {"iss": team_id, "sub": service_id, "iat": iat, "exp": exp}

    encoded_header = _encode_segment(header)
    encoded_payload = _encode_segment(payload)
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")

    private_key = _load_private_key(key_path)
    signature = _sign_es256(private_key, signing_input)
    return f"{encoded_header}.{encoded_payload}.{signature}"
