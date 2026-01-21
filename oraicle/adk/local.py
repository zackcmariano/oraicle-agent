"""
oraicle.adk.local

Small, opt-in helpers to make local development with `adk web` quieter/safer.

Why this exists:
- When running locally, some environments may partially initialize the
  `google.genai` HTTP client (used by Google-ADK) and later emit noisy logs on
  cleanup referencing internal fields like `_async_httpx_client`.
- This module provides a *surgical* guard that prevents those cleanup-time
  errors from surfacing when the client wasn't fully initialized.

This module is OPTIONAL. Import and call `configure_local_adk_web()` explicitly
if you want these guards.
"""

from __future__ import annotations

import os
from typing import Any


def configure_local_adk_web(*, allow_gemini_api_fallback: bool = True) -> None:
    """
    Apply small compatibility guards for local `adk web` runs.

    What this does:
    - Patches google-genai client cleanup to avoid noisy AttributeErrors related
      to `_async_httpx_client` when the client was only partially initialized.
    - Optionally toggles `GOOGLE_GENAI_USE_VERTEXAI` OFF when it's enabled but
      the environment looks incomplete for Vertex, and an API key is available.
      (This helps avoid "half-initialized client" scenarios in local dev.)
    """

    _patch_google_genai_async_httpx_cleanup()

    if allow_gemini_api_fallback:
        _maybe_disable_vertexai_if_incomplete_but_api_key_present()


def _maybe_disable_vertexai_if_incomplete_but_api_key_present() -> None:
    # ADK selects Vertex vs Gemini API based on GOOGLE_GENAI_USE_VERTEXAI.
    # If Vertex is enabled but project is missing, genai client init can fail.
    if not _env_enabled("GOOGLE_GENAI_USE_VERTEXAI"):
        return

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if project:
        return

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Nothing we can safely do: disabling Vertex would still not authenticate.
        return

    # Disable Vertex path so local dev can use the API key path instead.
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "0"


def _env_enabled(name: str) -> bool:
    v = os.getenv(name)
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _patch_google_genai_async_httpx_cleanup() -> None:
    """
    Patch `google.genai._api_client.BaseApiClient.aclose` to be a no-op when the
    client did not finish initializing `_async_httpx_client`.

    This prevents shutdown-time noise like "Task exception was never retrieved"
    with AttributeError on `_async_httpx_client` in local runs.
    """

    try:
        from google.genai._api_client import BaseApiClient  # type: ignore
    except Exception:
        return

    if getattr(BaseApiClient, "_oraicle_patched_async_httpx_cleanup", False):
        return

    original_aclose = BaseApiClient.aclose

    async def safe_aclose(self: Any) -> None:
        if not hasattr(self, "_async_httpx_client"):
            return
        await original_aclose(self)

    BaseApiClient.aclose = safe_aclose  # type: ignore[assignment]
    BaseApiClient._oraicle_patched_async_httpx_cleanup = True  # type: ignore[attr-defined]


