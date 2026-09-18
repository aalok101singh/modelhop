import time
from typing import AsyncIterator, Optional

from openai import AsyncOpenAI

from ...core.models import ProviderResponse
from .base import BaseProvider


class OpenAIProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, model, timeout_s=timeout_s, max_retries=max_retries)
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=0)

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        timeout_s: Optional[float] = None,
        tools: Optional[list] = None,
        **kwargs,
    ) -> ProviderResponse:
        start_time = time.time()

        async def _call():
            create_kwargs: dict = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if tools:
                create_kwargs["tools"] = tools
            create_kwargs.update(kwargs)
            # Per-call timeout via asyncio wrapper in _with_retries.
            return await self.client.chat.completions.create(**create_kwargs)

        response = await self._with_retries(_call, timeout_s=timeout_s)
        latency_ms = int((time.time() - start_time) * 1000)
        usage = getattr(response, "usage", None)
        return ProviderResponse(
            content=response.choices[0].message.content,
            model_used=self.model,
            provider="openai",
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
            raw_response=response,
        )

    async def stream(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        timeout_s: Optional[float] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        response = await self.generate(
            prompt, max_tokens=max_tokens, temperature=temperature, timeout_s=timeout_s, **kwargs
        )
        text = response.content or ""
        for i in range(0, len(text), 200):
            yield text[i : i + 200]

    async def validate_connection(self) -> bool:
        try:
            await self.generate("Hello", max_tokens=10, timeout_s=10)
            return True
        except Exception:
            return False
