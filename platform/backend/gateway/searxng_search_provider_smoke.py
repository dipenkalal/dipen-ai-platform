from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

from gateway.searxng_search_provider import (
    SEARXNG_ENDPOINT,
    SEARXNG_PROVIDER_ID,
    SearXNGWebSearchProvider,
)
from gateway.web_search_discovery import WebSearchRetrievalPipeline
from gateway.web_search_provider import WebSearchQuery
from tools.base import ToolExecutionResult

_SMOKE_QUERY = "Example Domain"
_SMOKE_OBJECTIVE = "Verify zero-cost local search discovery through the DAP boundary."


class _CaptureRetrievalTool:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, arguments: dict[str, Any]) -> ToolExecutionResult:
        self.calls.append(arguments)
        return ToolExecutionResult(
            tool_id="internet.research.retrieve",
            success=True,
            output={
                "smoke_capture_only": True,
                "requested_url_count": len(arguments.get("urls", [])),
            },
        )


async def _run() -> int:
    capture = _CaptureRetrievalTool()
    pipeline = WebSearchRetrievalPipeline(
        provider=SearXNGWebSearchProvider(),
        retrieval_tool=capture,
    )
    result = await pipeline.run(
        objective=_SMOKE_OBJECTIVE,
        query=WebSearchQuery(query=_SMOKE_QUERY, count=5),
    )

    selected_urls = result.selected_urls
    serialized_payload = result.model_dump(mode="json")
    checks = {
        "provider_id_exact": result.provider_id == SEARXNG_PROVIDER_ID,
        "endpoint_exact": SEARXNG_ENDPOINT == "http://127.0.0.1:8888/search",
        "query_exact": result.query == _SMOKE_QUERY,
        "candidate_count_nonzero": result.candidate_count > 0,
        "selected_count_bounded": 0 < len(selected_urls) <= 3,
        "all_selected_urls_https": all(
            urlsplit(url).scheme.lower() == "https" for url in selected_urls
        ),
        "retrieval_capture_called_once": len(capture.calls) == 1,
        "retrieval_urls_exact": bool(capture.calls)
        and tuple(capture.calls[0].get("urls", [])) == selected_urls,
        "retrieval_objective_exact": bool(capture.calls)
        and capture.calls[0].get("objective") == _SMOKE_OBJECTIVE,
        "provider_snippets_exposed_to_model_false": (
            result.provider_snippets_exposed_to_model is False
        ),
        "provider_titles_exposed_to_model_false": (
            result.provider_titles_exposed_to_model is False
        ),
        "search_candidates_are_evidence_false": (
            result.search_candidates_are_retrieval_evidence is False
        ),
        "candidate_urls_require_dap_retrieval_true": (
            result.candidate_urls_require_full_dap_retrieval is True
        ),
        "provider_credential_exposed_false": (
            result.provider_credential_exposed_to_model is False
        ),
        "generic_network_client_exposed_false": (
            result.generic_network_client_exposed is False
        ),
        "remote_scope_expansion_false": result.remote_scope_expansion_allowed is False,
        "knowledge_mutation_false": (
            result.automatic_knowledge_mutation_performed is False
        ),
        "task_ledger_mutation_false": result.task_ledger_mutation_performed is False,
        "guardian_contacted_false": result.guardian_contacted is False,
        "privileged_host_action_false": result.privileged_host_action_performed is False,
        "provider_titles_not_serialized": "provider_titles" not in serialized_payload,
        "provider_snippets_not_serialized": "provider_snippets" not in serialized_payload,
    }

    print("=== PHASE 12H ZERO-COST SEARXNG LIVE SEARCH SMOKE ===")
    print(f"provider_id|{result.provider_id}")
    print(f"provider_endpoint|{SEARXNG_ENDPOINT}")
    print(f"query|{result.query}")
    print(f"candidate_count|{result.candidate_count}")
    print(f"selected_url_count|{len(selected_urls)}")
    print(f"pipeline_id|{result.pipeline_id}")
    print(f"pipeline_sha256|{result.pipeline_sha256}")
    for index, url in enumerate(selected_urls, start=1):
        parsed = urlsplit(url)
        print(f"selected_{index}_scheme|{parsed.scheme}")
        print(f"selected_{index}_host|{parsed.hostname or ''}")
    for name, passed in checks.items():
        print(f"check|{name}|{str(passed).lower()}")
    print("paid_provider_used|false")
    print("provider_credential_required|false")
    print("model_called|false")
    print("database_write_performed|false")
    print("public_page_retrieval_performed_by_smoke|false")

    succeeded = all(checks.values())
    print(f"smoke_disposition|{'succeeded' if succeeded else 'failed'}")
    return 0 if succeeded else 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
