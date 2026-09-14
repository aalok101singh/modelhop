import time

from anthropic import AsyncAnthropic

from ...core.models import ProviderResponse
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key, model)
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        start_time = time.time()
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        latency_ms = int((time.time() - start_time) * 1000)
        return ProviderResponse(
            content=response.content[0].text,
            model_used=self.model,
            provider="anthropic",
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            latency_ms=latency_ms,
            raw_response=response
        )

    async def validate_connection(self) -> bool:
        try:
            await self.generate("Hello", max_tokens=10)
            return True
        except Exception:
            return False
