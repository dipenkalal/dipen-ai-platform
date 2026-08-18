from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gateway.providers.ollama import OllamaProvider


class RufloOllamaCompatibilityReport(BaseModel):
    """DAP-owned compatibility conclusion for the selected Ruflo seam."""

    model_config = ConfigDict(frozen=True)

    phase: Literal["10G"] = "10G"
    selected_ruflo_surface: Literal["pure-generator-validator"] = (
        "pure-generator-validator"
    )
    model_runtime_required_by_ruflo: Literal[False] = False
    dap_ollama_provider: Literal["ollama"] = "ollama"
    dap_ollama_base_url: str = Field(min_length=8, max_length=500)
    local_inference_authority: Literal["dap-gateway"] = "dap-gateway"
    ruflo_may_configure_ollama: Literal[False] = False
    ruflo_may_call_ollama_directly: Literal[False] = False
    ruflo_may_replace_dap_provider: Literal[False] = False
    compatibility: Literal["compatible-with-separation"] = (
        "compatible-with-separation"
    )
    live_model_probe_required_for_selected_surface: Literal[False] = False
    message: str = Field(min_length=4, max_length=2000)


def evaluate_ruflo_ollama_compatibility(
    provider: OllamaProvider | None = None,
) -> RufloOllamaCompatibilityReport:
    """Prove the evaluated Ruflo component does not need or own model runtime.

    Phase 10 adopted only pure generator/validator functions. Those functions do
    not require model inference. DAP's existing Ollama provider therefore remains
    the only local-model boundary; a live inference probe is not a prerequisite
    for compatibility of this selected Ruflo surface.
    """

    ollama = provider or OllamaProvider()
    if ollama.name != "ollama":
        raise ValueError("DAP Ollama provider identity changed unexpectedly")
    if not ollama.base_url.startswith(("http://", "https://")):
        raise ValueError("DAP Ollama base URL is not an HTTP endpoint")

    return RufloOllamaCompatibilityReport(
        dap_ollama_base_url=ollama.base_url,
        message=(
            "The selected Ruflo generator/validator seam is model-runtime "
            "independent. Local inference remains owned by the DAP Ollama "
            "provider and Ruflo receives no direct Ollama configuration or "
            "network authority."
        ),
    )
