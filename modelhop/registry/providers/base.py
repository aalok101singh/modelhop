from abc import ABC, abstractmethod
from ...core.models import ProviderResponse


class BaseProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.name = self.__class__.__name__

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> ProviderResponse:
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        pass
