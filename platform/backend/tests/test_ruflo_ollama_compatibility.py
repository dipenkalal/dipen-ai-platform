from engineering.ruflo_ollama_compatibility import (
    evaluate_ruflo_ollama_compatibility,
)
from gateway.providers.ollama import OllamaProvider


def test_selected_ruflo_surface_requires_no_model_runtime(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    report = evaluate_ruflo_ollama_compatibility()

    assert report.selected_ruflo_surface == "pure-generator-validator"
    assert report.model_runtime_required_by_ruflo is False
    assert report.local_inference_authority == "dap-gateway"
    assert report.ruflo_may_configure_ollama is False
    assert report.ruflo_may_call_ollama_directly is False
    assert report.ruflo_may_replace_dap_provider is False
    assert report.compatibility == "compatible-with-separation"
    assert report.live_model_probe_required_for_selected_surface is False


def test_existing_dap_ollama_provider_identity_is_preserved(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    provider = OllamaProvider()
    report = evaluate_ruflo_ollama_compatibility(provider)

    assert provider.name == "ollama"
    assert report.dap_ollama_provider == "ollama"
    assert report.dap_ollama_base_url == "http://localhost:11434"
