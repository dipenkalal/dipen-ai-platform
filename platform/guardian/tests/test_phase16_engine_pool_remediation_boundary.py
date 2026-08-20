from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
SETTINGS = REPO_ROOT / "deploy/phase12h-searxng/settings.yml"
PROVIDER = REPO_ROOT / "platform/backend/gateway/searxng_search_provider.py"
ROADMAP = REPO_ROOT / "docs/phase16-research-provider-coverage-latency-roadmap.md"

EXPECTED_ENGINES = {"bing", "wiby"}
EXCLUDED_UNQUALIFIED_ENGINES = {
    "google",
    "qwant",
    "mojeek",
    "wikipedia",
    "duckduckgo",
    "brave",
    "startpage",
}


def _keep_only_engines(source: str) -> set[str]:
    match = re.search(
        r"keep_only:\n(?P<body>(?:\s{6}- [^\n]+\n)+)",
        source,
    )
    if match is None:
        return set()
    return {
        line.strip().removeprefix("- ")
        for line in match.group("body").splitlines()
        if line.strip().startswith("- ")
    }


def _explicit_engine_states(source: str) -> dict[str, bool]:
    block_match = re.search(
        r"\nengines:\n(?P<body>.*?)(?=\n[a-z_]+:\n)",
        source,
        flags=re.DOTALL,
    )
    if block_match is None:
        return {}

    states: dict[str, bool] = {}
    current_name: str | None = None
    for raw_line in block_match.group("body").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- name: "):
            current_name = stripped.removeprefix("- name: ").strip()
        elif stripped.startswith("disabled: ") and current_name is not None:
            states[current_name] = stripped.removeprefix("disabled: ").strip() == "false"
    return states


class Phase16EnginePoolRemediationBoundaryTests(unittest.TestCase):
    def test_replacement_pool_is_exact_and_credential_free(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")

        self.assertEqual(_keep_only_engines(source), EXPECTED_ENGINES)
        states = _explicit_engine_states(source)
        self.assertEqual(set(states), EXPECTED_ENGINES)
        self.assertTrue(all(states.values()))

        lowered = source.lower()
        for prohibited in ("api_key", "token:", "secret_key", "password"):
            self.assertNotIn(prohibited, lowered)

    def test_unqualified_pool_is_removed_from_active_engine_selection(self) -> None:
        source = SETTINGS.read_text(encoding="utf-8")
        selected = _keep_only_engines(source) | set(_explicit_engine_states(source))

        self.assertTrue(EXCLUDED_UNQUALIFIED_ENGINES.isdisjoint(selected))

    def test_safe_search_and_local_service_shape_are_unchanged(self) -> None:
        settings = SETTINGS.read_text(encoding="utf-8")
        provider = PROVIDER.read_text(encoding="utf-8")

        self.assertIn("safe_search: 2", settings)
        self.assertIn('SEARXNG_HOST: Literal["127.0.0.1"] = "127.0.0.1"', provider)
        self.assertIn("SEARXNG_PORT = 8888", provider)
        self.assertIn('SEARXNG_PATH = "/search"', provider)
        self.assertIn('"categories": "general"', provider)
        self.assertIn('"safesearch": "2"', provider)

    def test_phase16_authority_invariants_remain_frozen(self) -> None:
        roadmap = ROADMAP.read_text(encoding="utf-8")

        self.assertIn("does **not** activate smart-routing research", roadmap)
        self.assertIn("provider remains `searxng-local-v1`", roadmap)
        self.assertIn("selected retrieval ceiling remains at most three URLs", roadmap)
        self.assertIn("no provider switching or arbitrary remote endpoint", roadmap)
        self.assertIn(
            "Any future authority expansion requires a separate owner-approved milestone.",
            roadmap,
        )


if __name__ == "__main__":
    unittest.main()
