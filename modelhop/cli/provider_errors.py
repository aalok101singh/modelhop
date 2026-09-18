"""Shared provider error classification + probes + fallback model catalog (CLI).

Used by `setup` (interactive model retry), `welcome` and `providers`
(honest status reasons instead of a bare "Failed").
"""

from __future__ import annotations

import asyncio
from typing import Optional

PROBE_TIMEOUT = 10

PROVIDER_DEFAULT_MODELS = {
    "groq": "qwen/qwen3.8-27b",
    "gemini": "gemini-3.6-flash",
    "openai": "gpt-4",
}

#: Candidate models probed (in order) when the configured default fails.
#: Providers rename/retire models over time; edit this catalog when they do.
PROVIDER_MODEL_FALLBACKS = {
    "groq": [
        "qwen/qwen3.8-27b",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
    ],
    "gemini": [
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ],
    "openai": [
        "gpt-4",
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4.1-mini",
    ],
}


def candidate_models(provider: str, configured: Optional[str] = None) -> list:
    """Configured model first, then catalog fallbacks (deduplicated)."""
    seen: list = []
    for m in [configured, *(PROVIDER_MODEL_FALLBACKS.get(provider, []))]:
        if m and m not in seen:
            seen.append(m)
    return seen


def _to_ascii(text: str, n: int = 140) -> str:
    """Collapse an API error excerpt to plain ASCII (piped output must stay
    ASCII-safe; user model *responses* are never passed through here)."""
    single = " ".join(str(text or "").split())
    for src, dst in (
        ("—", "-"),
        ("–", "-"),
        ("“", '"'),
        ("”", '"'),
        ("‘", "'"),
        ("’", "'"),
        ("…", "..."),
    ):
        single = single.replace(src, dst)
    single = single.encode("ascii", "replace").decode("ascii")
    return single[:n] + ("..." if len(single) > n else "")


def describe_provider_error(
    exc: BaseException, provider: str = "", model: str = ""
) -> tuple[str, str]:
    """Classify a provider exception -> (kind, short human message).

    Kinds: invalid_key | no_credits | model_not_found | rate_limited |
    network | error. Messages are plain ASCII by construction. Never raises;
    never leaks key material.
    """
    text = str(exc or "")
    low = text.lower()
    model_bit = f"model '{model}' " if model else "model "

    if (
        "incorrect api key" in low
        or "invalid api key" in low
        or "invalid_api_key" in low
        or "invalid x-api-key" in low
        or "authentication" in low
        or "unauthorized" in low
        or "error code: 401" in low
        or " 401 " in f" {low} "
    ):
        return "invalid_key", "invalid API key (401) - check the key and try again"
    if (
        "credit_balance_exhausted" in low
        or "insufficient_quota" in low
        or "no credits" in low
        or ("billing" in low and "credit" in low)
    ):
        if provider == "openai":
            return (
                "no_credits",
                "no credits remaining - add billing at "
                "platform.openai.com/settings/organization/billing",
            )
        return "no_credits", "no credits remaining - add billing on the provider dashboard"
    if "model_not_found" in low or "does not exist" in low or "error code: 404" in low:
        return (
            "model_not_found",
            f"{model_bit}not accessible to this account (404) - try another model",
        )
    if "error code: 429" in low or "rate_limit" in low or "rate limit" in low:
        return "rate_limited", "rate limited (429) - wait and retry"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)) or "timed out" in low:
        return "network", "connection timed out - check network and retry"
    if "connection" in low or "unreachable" in low or "dns" in low or "network" in low:
        return "network", "connection error - check network and retry"
    msg = _to_ascii(text)
    return ("error", msg if msg else "unknown error")


async def probe_model(
    provider: str, api_key: str, model: str, timeout: float = PROBE_TIMEOUT
) -> None:
    """Raise on failure; return None on success. Single shared probe."""
    if provider == "groq":
        from groq import AsyncGroq

        client = AsyncGroq(api_key=api_key, max_retries=0)
        await asyncio.wait_for(
            client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
            ),
            timeout=timeout,
        )
    elif provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        await asyncio.wait_for(m.generate_content_async("Hi"), timeout=timeout)
    elif provider == "openai":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=timeout)
        await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Hi"}], max_tokens=5
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def test_connection(
    provider: str, api_key: str, model: str, timeout: float = PROBE_TIMEOUT
) -> tuple[bool, str, str]:
    """Probe one model. Returns (ok, kind, detail)."""
    try:
        await probe_model(provider, api_key, model, timeout=timeout)
        return True, "ok", f"connected ({model})"
    except Exception as exc:
        kind, msg = describe_provider_error(exc, provider, model)
        return False, kind, msg
