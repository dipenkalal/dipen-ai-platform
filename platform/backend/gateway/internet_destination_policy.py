from __future__ import annotations

import hashlib
import ipaddress
import json
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ALLOWED_METHODS = frozenset({"GET", "HEAD"})
_BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "host.docker.internal",
        "gateway.docker.internal",
        "metadata.google.internal",
    }
)
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal")


class InternetDestinationRequest(BaseModel):
    """Resolver-supplied destination facts for a single URL admission."""

    model_config = ConfigDict(frozen=True)

    url: str = Field(min_length=1, max_length=8192)
    method: str = Field(default="GET", min_length=1, max_length=16)
    resolved_addresses: tuple[str, ...] = Field(min_length=1, max_length=16)
    redirect_depth: int = Field(default=0, ge=0, le=3)

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("destination URL must not be empty")
        return normalized

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("resolved_addresses")
    @classmethod
    def normalize_addresses(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(value.strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("resolved addresses must not be empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("resolved addresses must be unique")
        return normalized


class InternetDestinationFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(min_length=2, max_length=120)
    blocked: bool
    detail: str = Field(min_length=2, max_length=2000)


class InternetDestinationAdmission(BaseModel):
    """Immutable admission for one canonical public HTTPS destination."""

    model_config = ConfigDict(frozen=True)

    admission_id: str = Field(pattern=r"^internet-destination-[0-9a-f]{24}$")
    admission_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_url: str
    method: str
    hostname: str
    approved_addresses: tuple[str, ...]
    redirect_depth: int
    public_addresses_only: bool = True
    redirect_revalidation_required: bool = True
    transport_execution_enabled: bool = False


class InternetDestinationDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    disposition: str
    findings: tuple[InternetDestinationFinding, ...]
    admission: InternetDestinationAdmission | None = None


class InternetDestinationPolicy:
    """Pure SSRF policy. DNS resolution and HTTP transport live in later gates."""

    def evaluate(self, request: InternetDestinationRequest) -> InternetDestinationDecision:
        findings: list[InternetDestinationFinding] = []

        if request.method not in _ALLOWED_METHODS:
            findings.append(
                InternetDestinationFinding(
                    rule_id="unsupported-method",
                    blocked=True,
                    detail=f"Only GET/HEAD are admitted; observed {request.method!r}.",
                )
            )

        try:
            parsed = urlsplit(request.url)
            port = parsed.port
        except ValueError as exc:
            return self._reject("malformed-url", f"Malformed destination URL: {exc}")

        if parsed.scheme.lower() != "https":
            findings.append(
                InternetDestinationFinding(
                    rule_id="unsupported-scheme",
                    blocked=True,
                    detail="Only HTTPS destinations are admitted.",
                )
            )

        if parsed.username is not None or parsed.password is not None:
            findings.append(
                InternetDestinationFinding(
                    rule_id="url-credentials",
                    blocked=True,
                    detail="Credential-bearing URLs are prohibited.",
                )
            )

        if parsed.hostname is None:
            findings.append(
                InternetDestinationFinding(
                    rule_id="missing-hostname",
                    blocked=True,
                    detail="A destination hostname is required.",
                )
            )
            hostname = ""
        else:
            try:
                hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
            except UnicodeError:
                hostname = ""
                findings.append(
                    InternetDestinationFinding(
                        rule_id="invalid-hostname",
                        blocked=True,
                        detail="Destination hostname cannot be normalized safely.",
                    )
                )

        if port not in (None, 443):
            findings.append(
                InternetDestinationFinding(
                    rule_id="unsupported-port",
                    blocked=True,
                    detail="Initial public research retrieval permits HTTPS port 443 only.",
                )
            )

        if hostname and self._hostname_is_blocked(hostname):
            findings.append(
                InternetDestinationFinding(
                    rule_id="blocked-hostname",
                    blocked=True,
                    detail="Local, internal, container, and metadata hostnames are prohibited.",
                )
            )

        normalized_addresses: list[str] = []
        for raw_address in request.resolved_addresses:
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError:
                findings.append(
                    InternetDestinationFinding(
                        rule_id="invalid-resolved-address",
                        blocked=True,
                        detail=f"Resolver returned an invalid IP address: {raw_address!r}.",
                    )
                )
                continue

            normalized = address.compressed
            normalized_addresses.append(normalized)
            if not self._address_is_public(address):
                findings.append(
                    InternetDestinationFinding(
                        rule_id="non-public-address",
                        blocked=True,
                        detail=f"Resolved address {normalized} is not public internet space.",
                    )
                )

        if hostname:
            try:
                literal_address = ipaddress.ip_address(hostname)
            except ValueError:
                literal_address = None
            if literal_address is not None:
                literal = literal_address.compressed
                if literal not in normalized_addresses:
                    findings.append(
                        InternetDestinationFinding(
                            rule_id="literal-address-mismatch",
                            blocked=True,
                            detail="IP-literal URL does not match the resolver-supplied address set.",
                        )
                    )

        if any(finding.blocked for finding in findings):
            return InternetDestinationDecision(
                disposition="rejected",
                findings=tuple(findings),
            )

        canonical_url = self._canonical_url(parsed=parsed, hostname=hostname)
        approved_addresses = tuple(sorted(normalized_addresses))
        payload = {
            "canonical_url": canonical_url,
            "method": request.method,
            "hostname": hostname,
            "approved_addresses": list(approved_addresses),
            "redirect_depth": request.redirect_depth,
        }
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        admission_sha256 = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        admission = InternetDestinationAdmission(
            admission_id=f"internet-destination-{admission_sha256[:24]}",
            admission_sha256=admission_sha256,
            canonical_url=canonical_url,
            method=request.method,
            hostname=hostname,
            approved_addresses=approved_addresses,
            redirect_depth=request.redirect_depth,
        )
        return InternetDestinationDecision(
            disposition="accepted",
            findings=(),
            admission=admission,
        )

    @staticmethod
    def _hostname_is_blocked(hostname: str) -> bool:
        return hostname in _BLOCKED_HOSTS or hostname.endswith(_BLOCKED_HOST_SUFFIXES)

    @staticmethod
    def _address_is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return bool(
            address.is_global
            and not address.is_private
            and not address.is_loopback
            and not address.is_link_local
            and not address.is_multicast
            and not address.is_reserved
            and not address.is_unspecified
        )

    @staticmethod
    def _canonical_url(*, parsed: object, hostname: str) -> str:
        split = parsed
        scheme = getattr(split, "scheme").lower()
        path = getattr(split, "path") or "/"
        query = getattr(split, "query")
        netloc = f"[{hostname}]" if ":" in hostname else hostname
        return urlunsplit((scheme, netloc, path, query, ""))

    @staticmethod
    def _reject(rule_id: str, detail: str) -> InternetDestinationDecision:
        return InternetDestinationDecision(
            disposition="rejected",
            findings=(
                InternetDestinationFinding(
                    rule_id=rule_id,
                    blocked=True,
                    detail=detail,
                ),
            ),
        )


internet_destination_policy = InternetDestinationPolicy()
