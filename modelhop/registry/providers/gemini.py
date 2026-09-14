import os
import time
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai

from ...core.models import ProviderResponse
from .base import BaseProvider


class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        super().__init__(api_key, model)
        os.environ["GOOGLE_API_KEY"] = api_key
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        start_time = time.time()
        response = await self.client.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
        )
        latency_ms = int((time.time() - start_time) * 1000)
        return ProviderResponse(
            content=response.text,
            model_used=self.model,
            provider="gemini",
            tokens_in=response.usage_metadata.prompt_token_count,
            tokens_out=response.usage_metadata.candidates_token_count,
            latency_ms=latency_ms,
            raw_response=response
        )

    async def validate_connection(self) -> bool:
        try:
            await self.generate("Hello", max_tokens=10)
            return True
        except Exception:
            return False
