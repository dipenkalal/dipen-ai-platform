import pytest
from gateway.providers.base import AIProvider
from gateway.schemas import ChatRequest


def make_request() -> ChatRequest:
    # The abstract methods do not inspect the request.
    return ChatRequest.model_construct(messages=[])


@pytest.mark.asyncio
async def test_abstract_health_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await AIProvider.health(object())


@pytest.mark.asyncio
async def test_abstract_list_models_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await AIProvider.list_models(object())


@pytest.mark.asyncio
async def test_abstract_chat_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await AIProvider.chat(object(), make_request())


@pytest.mark.asyncio
async def test_abstract_stream_chat_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await AIProvider.stream_chat(object(), make_request())


def test_ai_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AIProvider()
