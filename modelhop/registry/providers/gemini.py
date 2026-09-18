import time
import warnings
from typing import AsyncIterator, Optional

warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai

from ...core.models import ProviderResponse
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.6-flash",
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key, model, timeout_s=timeout_s, max_retries=max_retries)
        # No global os.environ mutation (v1.1 security fix).
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

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
            gen_kwargs: dict = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
            extra = dict(kwargs)
            # `tools` is a request field, not a GenerationConfig field.
            tools_arg = tools if tools is not None else extra.pop("tools", None)
            gen_kwargs.update(extra)
            request_kwargs: dict = {
                "generation_config": genai.types.GenerationConfig(**gen_kwargs),
            }
            if tools_arg:
                request_kwargs["tools"] = tools_arg
            return await self.client.generate_content_async(prompt, **request_kwargs)

        response = await self._with_retries(_call, timeout_s=timeout_s)
        latency_ms = int((time.time() - start_time) * 1000)
        usage = getattr(response, "usage_metadata", None)
        return ProviderResponse(
            content=getattr(response, "text", ""),
            model_used=self.model,
            provider="gemini",
            tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
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
