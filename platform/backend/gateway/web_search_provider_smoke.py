from __future__ import annotations

import asyncio
import ipaddress
import os

from gateway.web_search_provider import (
    BRAVE_API_KEY_ENV,
    BRAVE_PROVIDER_ID,
    BraveWebSearchProvider,
    WebSearchProviderError,
    WebSearchQuery,
)

SMOKE_QUERY = "Example Domain"
SMOKE_COUNT = 3


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
    )


async def _run_smoke() -> int:
    token = os.environ.get(BRAVE_API_KEY_ENV, "")
    if not token:
        print("=== PHASE 12H LIVE SEARCH PROVIDER SMOKE FAILURE ===")
        print("error_code|provider-not-configured")
        print(f"required_env|{BRAVE_API_KEY_ENV}")
        print("provider_credential_printed|false")
        print("smoke_disposition|failed")
        return 1

    provider = BraveWebSearchProvider.from_environment()
    result = await provider.search(
        WebSearchQuery(query=SMOKE_QUERY, count=SMOKE_COUNT)
    )
    serialized = result.model_dump_json()
    checks = {
        "provider_id_exact": result.provider_id == BRAVE_PROVIDER_ID,
        "query_exact": result.query == SMOKE_QUERY,
        "candidate_count_nonzero": len(result.candidates) > 0,
        "provider_address_public": _is_public_address(result.connected_address),
        "all_candidate_urls_https": all(
            candidate.url.startswith("https://") for candidate in result.candidates
        ),
        "all_candidates_untrusted": all(
            candidate.candidate_is_untrusted for candidate in result.candidates
        ),
        "all_candidates_not_evidence": all(
            not candidate.candidate_is_retrieval_evidence
            for candidate in result.candidates
        ),
        "all_candidates_require_dap_retrieval": all(
            candidate.candidate_url_requires_dap_retrieval
            for candidate in result.candidates
        ),
        "provider_credential_not_serialized": token not in serialized,
        "provider_credential_model_exposure_false": (
            not result.provider_credential_exposed_to_model
        ),
        "provider_credential_persistence_false": not result.provider_credential_persisted,
        "provider_credential_forwarding_false": (
            not result.provider_credential_forwarded_to_result_url
        ),
        "generic_network_client_false": not result.generic_network_client_exposed,
        "knowledge_mutation_false": not result.automatic_knowledge_mutation_performed,
        "task_ledger_mutation_false": not result.task_ledger_mutation_performed,
        "guardian_contacted_false": not result.guardian_contacted,
        "privileged_host_action_false": not result.privileged_host_action_performed,
    }

    print("=== PHASE 12H LIVE SEARCH PROVIDER SMOKE ===")
    print(f"provider_id|{result.provider_id}")
    print(f"query|{result.query}")
    print(f"requested_count|{result.requested_count}")
    print(f"candidate_count|{len(result.candidates)}")
    print(f"dropped_unsafe_candidate_count|{result.dropped_unsafe_candidate_count}")
    print(f"provider_connected_address|{result.connected_address}")
    print(f"provider_address_public|{str(_is_public_address(result.connected_address)).lower()}")
    print(f"discovery_id|{result.discovery_id}")
    print(f"discovery_sha256|{result.discovery_sha256}")
    print(f"raw_response_sha256|{result.raw_response_sha256}")
    for name, passed in checks.items():
        print(f"check|{name}|{str(passed).lower()}")
    print("provider_credential_printed|false")
    print("search_snippets_printed|false")
    print("search_candidates_are_retrieval_evidence|false")
    print("candidate_urls_require_full_dap_retrieval|true")
    print("agent_search_tool_registered|false")

    passed = all(checks.values())
    print(f"smoke_disposition|{'succeeded' if passed else 'failed'}")
    return 0 if passed else 1


def main() -> int:
    try:
        return asyncio.run(_run_smoke())
    except WebSearchProviderError as exc:
        print("=== PHASE 12H LIVE SEARCH PROVIDER SMOKE FAILURE ===")
        print(f"error_code|{exc.code}")
        print(f"error_detail|{exc.detail}")
        print("provider_credential_printed|false")
        print("smoke_disposition|failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
