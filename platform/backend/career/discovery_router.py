from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final


PROVIDER_SPECIFIC_CONNECTOR: Final = (
    "PROVIDER_SPECIFIC_CONNECTOR"
)

GENERIC_PHASE16_FALLBACK: Final = (
    "GENERIC_PHASE16_FALLBACK"
)

FAIL_CLOSED: Final = "FAIL_CLOSED"


EMPTY_PROVIDER_KIND: Final = "EMPTY_PROVIDER_KIND"
UNKNOWN_PROVIDER: Final = "UNKNOWN_PROVIDER"
MISSING_PROVIDER_TARGET: Final = "MISSING_PROVIDER_TARGET"
INVALID_PROVIDER_TARGET: Final = "INVALID_PROVIDER_TARGET"
UNAUTHORIZED_GENERIC_FALLBACK: Final = (
    "UNAUTHORIZED_GENERIC_FALLBACK"
)
ROUTER_CONFIGURATION_ERROR: Final = (
    "ROUTER_CONFIGURATION_ERROR"
)


_ROUTE_POLICY: Final = MappingProxyType(
    {
        "greenhouse": (
            PROVIDER_SPECIFIC_CONNECTOR,
            "career.connectors.greenhouse",
        ),
        "lever": (
            PROVIDER_SPECIFIC_CONNECTOR,
            "career.connectors.lever",
        ),
        "ashby": (
            PROVIDER_SPECIFIC_CONNECTOR,
            "career.connectors.ashby",
        ),
        "smartrecruiters": (
            PROVIDER_SPECIFIC_CONNECTOR,
            "career.connectors.smartrecruiters",
        ),
        "workday": (
            GENERIC_PHASE16_FALLBACK,
            None,
        ),
    }
)


@dataclass(frozen=True, slots=True)
class DiscoveryRouteDecision:
    provider_kind: str
    route_kind: str
    connector_module: str | None
    provider_target: Mapping[str, Any] | None
    phase16_network_owner: bool
    endpoint: None
    network_request_created_by_router: bool
    reason: str


def frozen_route_policy() -> Mapping[
    str,
    tuple[str, str | None],
]:
    """Return the immutable frozen provider routing policy."""

    return _ROUTE_POLICY


def _fail_closed(
    *,
    provider_kind: str,
    provider_target: Mapping[str, Any] | None,
    reason: str,
) -> DiscoveryRouteDecision:
    return DiscoveryRouteDecision(
        provider_kind=provider_kind,
        route_kind=FAIL_CLOSED,
        connector_module=None,
        provider_target=provider_target,
        phase16_network_owner=True,
        endpoint=None,
        network_request_created_by_router=False,
        reason=reason,
    )


def resolve_discovery_route(
    provider_kind: str,
    provider_target: Mapping[str, Any] | None = None,
    *,
    research_request_context: Mapping[str, Any] | None = None,
) -> DiscoveryRouteDecision:
    """
    Resolve a Career provider to its frozen offline route.

    The router performs no retrieval, endpoint inference, credential
    lookup, database access, or network activity. The optional research
    context is deliberately opaque to routing and cannot grant authority.
    """

    del research_request_context

    if not isinstance(provider_kind, str):
        return _fail_closed(
            provider_kind="",
            provider_target=(
                provider_target
                if isinstance(provider_target, Mapping)
                else None
            ),
            reason=EMPTY_PROVIDER_KIND,
        )

    normalized = provider_kind.strip().lower()

    if not normalized:
        return _fail_closed(
            provider_kind="",
            provider_target=(
                provider_target
                if isinstance(provider_target, Mapping)
                else None
            ),
            reason=EMPTY_PROVIDER_KIND,
        )

    route = _ROUTE_POLICY.get(
        normalized
    )

    if route is None:
        return _fail_closed(
            provider_kind=normalized,
            provider_target=(
                provider_target
                if isinstance(provider_target, Mapping)
                else None
            ),
            reason=UNKNOWN_PROVIDER,
        )

    if provider_target is None:
        return _fail_closed(
            provider_kind=normalized,
            provider_target=None,
            reason=MISSING_PROVIDER_TARGET,
        )

    if not isinstance(
        provider_target,
        Mapping,
    ):
        return _fail_closed(
            provider_kind=normalized,
            provider_target=None,
            reason=INVALID_PROVIDER_TARGET,
        )

    route_kind, connector_module = route

    return DiscoveryRouteDecision(
        provider_kind=normalized,
        route_kind=route_kind,
        connector_module=connector_module,
        provider_target=provider_target,
        phase16_network_owner=True,
        endpoint=None,
        network_request_created_by_router=False,
        reason=(
            "KNOWN_PROVIDER_ROUTE"
            if route_kind
            == PROVIDER_SPECIFIC_CONNECTOR
            else "WORKDAY_GENERIC_PHASE16_FALLBACK"
        ),
    )
