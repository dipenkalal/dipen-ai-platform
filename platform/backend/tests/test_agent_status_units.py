from agents.executor import AgentExecutor


def test_status_prompt_humanizes_ollama_sizes() -> None:
    raw = {
        "ollama": {
            "online": True,
            "loaded_models": [
                {
                    "name": "qwen3:1.7b",
                    "size": 1882424605,
                    "size_vram": 0,
                }
            ],
        }
    }

    normalized = (
        AgentExecutor._normalize_status_for_prompt(
            raw
        )
    )

    model = normalized["ollama"][
        "loaded_models"
    ][0]

    assert model["size"] == 1882424605
    assert model["size_human"] == "1.75 GiB"

    assert model["size_vram"] == 0
    assert model["size_vram_human"] == "0 B"

    # Raw tool evidence must not be mutated.
    assert "size_human" not in (
        raw["ollama"]["loaded_models"][0]
    )


def test_humanize_bytes_handles_mebibytes() -> None:
    assert (
        AgentExecutor._humanize_bytes(
            680379023
        )
        == "648.86 MiB"
    )
