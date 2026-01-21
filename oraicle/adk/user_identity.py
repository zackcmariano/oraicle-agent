"""
oraicle.adk.user_identity

Utilities to derive a human-readable `user_id` to be used when querying an ADK
agent deployed on Vertex AI Agent Engine.

Why this exists:
- Agent Engine "Sessions" shows a "User ID" column.
- ADK's Agent Engine template uses `user_id=` to set that value.
- In Playground / Gemini Enterprise, user identity commonly arrives via headers
  (or a JWT). This module extracts a stable identifier without requiring any
  dependency on Vertex/ADK or specific web frameworks.

This module is OPTIONAL and does not affect Oraicle's existing behavior unless
you import and use it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional
import base64
import json


@dataclass(frozen=True)
class ResolvedUserIdentity:
    """
    Represents the resolved identity and the source used to resolve it.
    """

    user_id: str
    source: str


def get_agent_engine_user_id(
    *,
    explicit_user: str | None = None,
    request: Any | None = None,
    headers: Mapping[str, str] | None = None,
    default: str = "anonymous",
) -> str:
    """
    Convenience helper: return only the `user_id` string (instead of the full
    `ResolvedUserIdentity` object).

    This is intentionally a thin wrapper around `agent_engine_user_id()` so
    callers can do a one-liner without defining their own helper function:

        user_id = get_agent_engine_user_id(explicit_user=user, request=request)
    """

    return agent_engine_user_id(
        explicit_user=explicit_user,
        request=request,
        headers=headers,
        default=default,
    ).user_id


def resolve_agent_engine_user_id(
    *,
    explicit_user: str | None = None,
    request: Any | None = None,
    headers: Mapping[str, str] | None = None,
    default: str = "anonymous",
) -> ResolvedUserIdentity:
    """
    Backward-compatible alias for `agent_engine_user_id()`.

    Kept to avoid breaking early adopters of this feature.
    """

    return agent_engine_user_id(
        explicit_user=explicit_user,
        request=request,
        headers=headers,
        default=default,
    )


def agent_engine_user_id(
    *,
    explicit_user: str | None = None,
    request: Any | None = None,
    headers: Mapping[str, str] | None = None,
    default: str = "anonymous",
) -> ResolvedUserIdentity:
    """
    Resolve a human-readable `user_id` to be passed to ADK Agent Engine calls.

    Resolution order (first match wins):
    1) explicit_user
    2) request.headers / provided headers (common identity headers)
    3) JWT in Authorization / IAP assertion headers (decode only; no verification)
    4) default
    """

    # 1) Explicit (caller-provided)
    if explicit_user is not None:
        normalized = _normalize_user_id(explicit_user)
        return ResolvedUserIdentity(user_id=normalized or default, source="explicit_user")

    hdrs = _coerce_headers(request=request, headers=headers)

    # 2) Common identity headers (case-insensitive)
    # - IAP / Cloud Run / proxy patterns
    # - Agent Engine / Google frontends sometimes forward authenticated identity
    header_candidates = [
        "x-goog-authenticated-user-name",
        "x-goog-user-name",
        "x-forwarded-preferred-username",
        "x-forwarded-user",
        "x-forwarded-email",
        "x-goog-authenticated-user-email",
        "x-goog-user-email",
    ]
    for key in header_candidates:
        val = _header_get(hdrs, key)
        if val:
            cleaned = _clean_google_identity_header(val)
            normalized = _normalize_user_id(cleaned)
            if normalized:
                return ResolvedUserIdentity(user_id=normalized, source=f"header:{key}")

    # 3) JWT-based sources (decode only; no signature verification)
    jwt_sources = [
        ("authorization", _header_get(hdrs, "authorization")),
        ("x-goog-iap-jwt-assertion", _header_get(hdrs, "x-goog-iap-jwt-assertion")),
    ]
    for source_name, raw in jwt_sources:
        token = _extract_bearer(raw) if source_name == "authorization" else raw
        claims = _decode_jwt_claims_no_verify(token)
        if not claims:
            continue
        for claim_key in ("name", "email", "preferred_username", "upn", "sub"):
            if claim_key in claims and claims[claim_key]:
                normalized = _normalize_user_id(str(claims[claim_key]))
                if normalized:
                    return ResolvedUserIdentity(
                        user_id=normalized, source=f"jwt:{source_name}:{claim_key}"
                    )

    # 4) Default
    return ResolvedUserIdentity(user_id=default, source="default")


def _coerce_headers(
    *, request: Any | None, headers: Mapping[str, str] | None
) -> Mapping[str, str]:
    if headers is not None:
        return headers
    if request is None:
        return {}
    req_headers = getattr(request, "headers", None)
    return req_headers if isinstance(req_headers, Mapping) else {}


def _header_get(headers: Mapping[str, str], key: str) -> Optional[str]:
    # Case-insensitive lookup without copying for most common patterns.
    if not headers:
        return None
    if key in headers:
        return headers.get(key)
    lower_key = key.lower()
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == lower_key:
            return v
    return None


def _clean_google_identity_header(value: str) -> str:
    """
    Normalize patterns like:
    - "accounts.google.com:someone@corp.com"
    - "accounts.google.com:1234567890"
    """
    v = value.strip()
    if ":" in v:
        prefix, rest = v.split(":", 1)
        if prefix.endswith("google.com") or prefix.endswith("googleusercontent.com"):
            return rest.strip()
    return v


def _extract_bearer(authorization_value: str | None) -> str | None:
    if not authorization_value:
        return None
    v = authorization_value.strip()
    parts = v.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _decode_jwt_claims_no_verify(token: str | None) -> dict | None:
    """
    Decode a JWT payload WITHOUT verifying signature.
    Safe to use only for display/user-id purposes, never for authorization.
    """
    if not token or token.count(".") < 2:
        return None
    try:
        _header_b64, payload_b64, _sig_b64 = token.split(".", 2)
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _b64url_decode(data: str) -> bytes:
    s = data.encode("utf-8")
    s += b"=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode(s)


def _normalize_user_id(value: str) -> str:
    """
    Produce a compact, safe, human-readable identifier.
    """
    v = (value or "").strip()
    if not v:
        return ""
    # Collapse excessive whitespace
    v = " ".join(v.split())
    # Avoid extremely long identifiers in Agent Engine UI
    if len(v) > 128:
        v = v[:125] + "..."
    return v


