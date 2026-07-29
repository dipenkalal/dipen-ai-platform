import pytest
from gateway.providers.ollama import OllamaProvider
from gateway.schemas import ChatMessage, ChatRequest


def make_request(
    *,
    model: str | None = "test-model",
    max_tokens: int | None = 256,
    temperature: float = 0.4,
) -> ChatRequest:
    return ChatRequest(
        provider="ollama",
        model=model,
        messages=[
            ChatMessage(
                role="system",
                content="You are helpful.",
            ),
            ChatMessage(
                role="user",
                content="Hello",
            ),
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("1", True),
        ("true", True),
        ("TRUE", True),
        (" yes ", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("off", False),
        ("unexpected", False),
        ("", False),
    ],
)
def test_read_boolean_env_parses_values(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv(
        "TEST_BOOLEAN_VALUE",
        raw_value,
    )

    assert (
        OllamaProvider._read_boolean_env(
            "TEST_BOOLEAN_VALUE",
            default=False,
        )
        is expected
    )


def test_read_boolean_env_uses_default_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "TEST_BOOLEAN_VALUE",
        raising=False,
    )

    assert (
        OllamaProvider._read_boolean_env(
            "TEST_BOOLEAN_VALUE",
            default=True,
        )
        is True
    )

    assert (
        OllamaProvider._read_boolean_env(
            "TEST_BOOLEAN_VALUE",
            default=False,
        )
        is False
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  hello  ", "hello"),
        ("", ""),
        ("   ", ""),
        (None, ""),
        (123, ""),
        ({"content": "hello"}, ""),
        (["hello"], ""),
    ],
)
def test_clean_text(
    value: object,
    expected: str,
) -> None:
    assert OllamaProvider._clean_text(value) == expected


@pytest.mark.parametrize(
    ("prompt_tokens", "completion_tokens", "expected"),
    [
        (10, 5, 15),
        (0, 0, 0),
        (0, 7, 7),
        (12, 0, 12),
        (None, 5, None),
        (10, None, None),
        (None, None, None),
    ],
)
def test_calculate_total_tokens(
    prompt_tokens: int | None,
    completion_tokens: int | None,
    expected: int | None,
) -> None:
    assert (
        OllamaProvider._calculate_total_tokens(
            prompt_tokens,
            completion_tokens,
        )
        == expected
    )


def test_empty_response_error_for_reasoning_token_limit() -> None:
    error = OllamaProvider._empty_response_error(
        model="reasoning-model",
        done_reason="length",
        has_thinking=True,
    )

    assert isinstance(error, RuntimeError)
    assert "exhausted its token budget" in str(error)
    assert "reasoning-model" in str(error)
    assert "increase max_tokens" in str(error)
    assert "OLLAMA_THINKING_ENABLED" in str(error)


def test_empty_response_error_for_normal_token_limit() -> None:
    error = OllamaProvider._empty_response_error(
        model="test-model",
        done_reason="length",
        has_thinking=False,
    )

    assert isinstance(error, RuntimeError)
    assert "reached its token limit" in str(error)
    assert "Increase max_tokens" in str(error)


def test_empty_response_error_for_thinking_without_answer() -> None:
    error = OllamaProvider._empty_response_error(
        model="thinking-model",
        done_reason="stop",
        has_thinking=True,
    )

    assert isinstance(error, RuntimeError)
    assert "returned reasoning output" in str(error)
    assert "no final answer" in str(error)


def test_empty_response_error_for_empty_response() -> None:
    error = OllamaProvider._empty_response_error(
        model="empty-model",
        done_reason=None,
        has_thinking=False,
    )

    assert isinstance(error, RuntimeError)
    assert str(error) == ("Model 'empty-model' returned an empty response.")


def test_provider_initialises_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://ollama.internal:11434/",
    )
    monkeypatch.setenv(
        "OLLAMA_DEFAULT_MODEL",
        "qwen-test:latest",
    )
    monkeypatch.setenv(
        "OLLAMA_THINKING_ENABLED",
        "true",
    )

    provider = OllamaProvider()

    assert provider.base_url == ("http://ollama.internal:11434")
    assert provider.default_model == "qwen-test:latest"
    assert provider.thinking_enabled is True


def test_provider_uses_default_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "OLLAMA_BASE_URL",
        raising=False,
    )
    monkeypatch.delenv(
        "OLLAMA_DEFAULT_MODEL",
        raising=False,
    )
    monkeypatch.delenv(
        "OLLAMA_THINKING_ENABLED",
        raising=False,
    )

    provider = OllamaProvider()

    assert provider.base_url == ("http://127.0.0.1:11434")
    assert provider.default_model == "qwen3:1.7b"
    assert provider.thinking_enabled is False


def test_create_payload_with_explicit_model() -> None:
    provider = OllamaProvider()
    provider.thinking_enabled = True

    request = make_request(
        model="explicit-model",
        max_tokens=512,
        temperature=0.25,
    )

    payload = provider._create_payload(
        request,
        stream=False,
    )

    assert payload == {
        "model": "explicit-model",
        "messages": [
            {
                "role": "system",
                "content": "You are helpful.",
            },
            {
                "role": "user",
                "content": "Hello",
            },
        ],
        "stream": False,
        "think": True,
        "options": {
            "temperature": 0.25,
            "num_predict": 512,
        },
    }


def test_create_payload_uses_default_model() -> None:
    provider = OllamaProvider()
    provider.default_model = "default-test-model"
    provider.thinking_enabled = False

    request = make_request(
        model=None,
        max_tokens=128,
    )

    payload = provider._create_payload(
        request,
        stream=True,
    )

    assert payload["model"] == "default-test-model"
    assert payload["stream"] is True
    assert payload["think"] is False
    assert payload["options"]["num_predict"] == 128


def test_create_payload_omits_num_predict_when_unset() -> None:
    provider = OllamaProvider()

    request = make_request(
        max_tokens=None,
    )

    payload = provider._create_payload(
        request,
        stream=False,
    )

    assert payload["options"] == {
        "temperature": 0.4,
    }


def test_create_payload_does_not_mutate_request() -> None:
    provider = OllamaProvider()
    request = make_request()

    original = request.model_dump()

    provider._create_payload(
        request,
        stream=True,
    )

    assert request.model_dump() == original
