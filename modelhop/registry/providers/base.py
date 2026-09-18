from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from ...core.models import ProviderResponse


def _jittered_delay(attempt: int, base: float = 0.5, cap: float = 8.0) -> float:
    delay = min(cap, base * (2**attempt))
    return delay * (0.5 + random.random() * 0.5)


class BaseProvider(ABC):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.name = self.__class__.__name__
        self.timeout_s = float(timeout_s or 30.0)
        self.max_retries = int(max_retries if max_retries is not None else 2)

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        timeout_s: Optional[float] = None,
        tools: Optional[list] = None,
        **kwargs,
    ) -> ProviderResponse:
        pass

    async def stream(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Default streaming fallback: single generate, then yield in chunks."""
        response = await self.generate(
            prompt, max_tokens=max_tokens, temperature=temperature, timeout_s=timeout_s, **kwargs
        )
        text = response.content or ""
        chunk = 200
        for i in range(0, len(text), chunk):
            yield text[i : i + chunk]

    async def _with_retries(self, coro_fn, *, timeout_s: Optional[float] = None):
        timeout = float(timeout_s or self.timeout_s)
        last_exc: Optional[Exception] = None
        attempts = max(1, self.max_retries + 1)
        for attempt in range(attempts):
            try:
                return await asyncio.wait_for(coro_fn(), timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - bounded retry then raise
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                # Only retry transient errors.
                msg = str(exc).lower()
                transient = any(
                    t in msg
                    for t in (
                        "429",
                        "rate",
                        "timeout",
                        "temporar",
                        "503",
                        "502",
                        "504",
                        "overload",
                        "connection",
                        "timed out",
                    )
                )
                if not transient and "asyncio" not in type(exc).__name__.lower():
                    # For unknown errors, still retry once if attempts allow,
                    # except auth errors which are never transient.
                    if any(t in msg for t in ("401", "403", "auth", "invalid api", "permission")):
                        break
                await asyncio.sleep(_jittered_delay(attempt))
        assert last_exc is not None
        raise last_exc

    @abstractmethod
    async def validate_connection(self) -> bool:
        pass
