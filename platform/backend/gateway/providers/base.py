from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from gateway.schemas import ChatRequest, ChatResponse, ModelInfo


class AIProvider(ABC):
    name: str

    @abstractmethod
    async def health(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        raise NotImplementedError

    @abstractmethod
    def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
