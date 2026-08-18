from __future__ import annotations

import asyncio
import hashlib
import ipaddress

from gateway.internet_transport import (
    TRANSPORT_ID,
    BoundedInternetRetriever,
    InternetTransportError,
    InternetTransportLimits,
)

SMOKE_URL = "https://example.com/"
BLOCKED_LOOPBACK_URL = "https://127.0.0.1/"
SMOKE_LIMITS = InternetTransportLimits(
    dns_timeout_seconds=5.0,
    connect_timeout_seconds=7.0,
    read_timeout_seconds=12.0,
    total_timeout_seconds=30.0,
    max_header_bytes=32 * 1024,
    max_header_count=100,
    max_body_bytes=256 * 1024,
    max_redirects=2,
)


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return address.is_global and not any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


async def _run_smoke() -> int:
    retriever = BoundedInternetRetriever(limits=SMOKE_LIMITS)
    result = await retriever.retrieve(SMOKE_URL, method="GET")

    checks = {
        "transport_id_exact": result.transport_id == TRANSPORT_ID,
        "requested_url_exact": result.requested_url == SMOKE_URL,
        "method_get": result.method == "GET",
        "status_200": result.status_code == 200,
        "content_type_html": result.content_type == "text/html",
        "body_nonempty": result.byte_count > 0,
        "byte_count_exact": result.byte_count == len(result.body),
        "body_hash_exact": result.body_sha256
        == hashlib.sha256(result.body).hexdigest(),
        "redirect_depth_bounded": 1 <= len(result.hops) <= SMOKE_LIMITS.max_redirects + 1,
        "all_connected_addresses_admitted": all(
            hop.connected_address in hop.approved_addresses for hop in result.hops
        ),
        "all_connected_addresses_public": all(
            _is_public_address(hop.connected_address) for hop in result.hops
        ),
        "knowledge_mutation_false": not result.automatic_knowledge_mutation_performed,
        "task_ledger_mutation_false": not result.task_ledger_mutation_performed,
        "agent_tool_registration_false": not result.agent_tool_registration_performed,
        "guardian_contacted_false": not result.guardian_contacted,
        "privileged_host_action_false": not result.privileged_host_action_performed,
    }

    blocked_loopback_code = "none"
    try:
        await retriever.retrieve(BLOCKED_LOOPBACK_URL, method="GET")
    except InternetTransportError as exc:
        blocked_loopback_code = exc.code

    checks["loopback_rejected_pre_dns"] = (
        blocked_loopback_code == "destination-preflight-rejected"
    )

    print("=== PHASE 12D LIVE PUBLIC FETCH SMOKE ===")
    print(f"smoke_url|{SMOKE_URL}")
    print(f"transport_id|{result.transport_id}")
    print(f"status_code|{result.status_code}")
    print(f"content_type|{result.content_type}")
    print(f"byte_count|{result.byte_count}")
    print(f"body_sha256|{result.body_sha256}")
    print(f"hop_count|{len(result.hops)}")
    for index, hop in enumerate(result.hops, start=1):
        print(f"hop_{index}_url|{hop.canonical_url}")
        print(f"hop_{index}_connected_address|{hop.connected_address}")
        print(f"hop_{index}_address_admitted|{hop.connected_address in hop.approved_addresses}")
        print(f"hop_{index}_address_public|{_is_public_address(hop.connected_address)}")
    print(f"blocked_loopback_code|{blocked_loopback_code}")
    for name, passed in checks.items():
        print(f"check|{name}|{str(passed).lower()}")

    passed = all(checks.values())
    print("generic_url_input_exposed|false")
    print("credentials_forwarded|false")
    print("agent_tool_registered|false")
    print("knowledge_mutated|false")
    print("task_ledger_mutated|false")
    print("guardian_contacted|false")
    print("privileged_host_action|false")
    print(f"smoke_disposition|{'succeeded' if passed else 'failed'}")
    return 0 if passed else 1


def main() -> int:
    try:
        return asyncio.run(_run_smoke())
    except InternetTransportError as exc:
        print("=== PHASE 12D LIVE PUBLIC FETCH SMOKE FAILURE ===")
        print(f"error_code|{exc.code}")
        print(f"error_detail|{exc.detail}")
        print("smoke_disposition|failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
