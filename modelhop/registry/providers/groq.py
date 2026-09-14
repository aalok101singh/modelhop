import time
from groq import AsyncGroq
from .base import BaseProvider
from ...core.models import ProviderResponse


class GroqProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        super().__init__(api_key, model)
        self.client = AsyncGroq(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        start_time = time.time()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        latency_ms = int((time.time() - start_time) * 1000)
        return ProviderResponse(
            content=response.choices[0].message.content,
            model_used=self.model,
            provider="groq",
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            latency_ms=latency_ms,
            raw_response=response
        )

    async def validate_connection(self) -> bool:
        try:
            await self.generate("Hello", max_tokens=10)
            return True
        except Exception:
            return False
