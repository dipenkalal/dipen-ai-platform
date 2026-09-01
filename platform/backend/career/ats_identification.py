from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from urllib.parse import (
    SplitResult,
    urlsplit,
    urlunsplit,
)

from career.provider_identity import (
    canonicalize_provider_identity,
)


_GREENHOUSE_HOSTS = frozenset({
    "job-boards.greenhouse.io",
    "job-boards.eu.greenhouse.io",
})

_LEVER_HOST = "jobs.lever.co"

_ASHBY_HOST = "jobs.ashbyhq.com"

_SMART_PUBLIC_HOSTS = frozenset({
    "careers.smartrecruiters.com",
    "jobs.smartrecruiters.com",
})

_SMART_API_HOST = (
    "api.smartrecruiters.com"
)

_WORKDAY_HOST_RE = re.compile(
    r"^(?P<tenant>[a-z0-9]"
    r"[a-z0-9-]{0,126})"
    r"\.wd[0-9]+"
    r"\.myworkdayjobs\.com$"
)

_OPAQUE_SEGMENT_RE = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._-]{0,127}$"
)

_LOCALE_RE = re.compile(
    r"^[A-Za-z]{2}"
    r"(?:-[A-Za-z]{2})?$"
)


class ATSIdentificationError(
    ValueError
):
    pass


class ATSIdentificationStatus(
    StrEnum
):
    UNRECOGNIZED = "unrecognized"
    ATS_IDENTIFIED = "ats_identified"
    ENDPOINT_IDENTIFIED = (
        "endpoint_identified"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ATSIdentificationResult:

    input_url: str
    status: ATSIdentificationStatus

    provider_kind: str | None = None

    canonical_career_url: str | None = None

    provider_identity_key: str | None = None

    provider_identity_json: str | None = None

    provider_identity_sha256: str | None = None

    def __post_init__(self) -> None:

        status = ATSIdentificationStatus(
            self.status
        )

        object.__setattr__(
            self,
            "status",
            status,
        )

        identity_values = (
            self.provider_identity_key,
            self.provider_identity_json,
            self.provider_identity_sha256,
        )

        identity_present = [
            value is not None
            for value in identity_values
        ]

        if (
            status
            == ATSIdentificationStatus.UNRECOGNIZED
        ):

            if (
                self.provider_kind is not None
                or self.canonical_career_url
                is not None
                or any(identity_present)
            ):
                raise ATSIdentificationError(
                    "unrecognized result may not "
                    "carry provider identity"
                )

        elif (
            status
            == ATSIdentificationStatus.ATS_IDENTIFIED
        ):

            if self.provider_kind is None:
                raise ATSIdentificationError(
                    "ats_identified requires "
                    "provider_kind"
                )

            if (
                self.canonical_career_url
                is not None
                or any(identity_present)
            ):
                raise ATSIdentificationError(
                    "ats_identified may not claim "
                    "endpoint identity"
                )

        elif (
            status
            == ATSIdentificationStatus.ENDPOINT_IDENTIFIED
        ):

            if self.provider_kind is None:
                raise ATSIdentificationError(
                    "endpoint_identified requires "
                    "provider_kind"
                )

            if self.canonical_career_url is None:
                raise ATSIdentificationError(
                    "endpoint_identified requires "
                    "canonical_career_url"
                )

            if not all(identity_present):
                raise ATSIdentificationError(
                    "endpoint_identified requires "
                    "complete provider identity"
                )


def _validated_url(
    value: str,
) -> tuple[
    str,
    SplitResult,
    str,
]:

    if not isinstance(value, str):
        raise ATSIdentificationError(
            "career URL must be string"
        )

    if value != value.strip():
        raise ATSIdentificationError(
            "career URL must already be normalized"
        )

    if not value:
        raise ATSIdentificationError(
            "career URL may not be empty"
        )

    if any(
        ord(character) < 0x20
        or ord(character) == 0x7F
        for character in value
    ):
        raise ATSIdentificationError(
            "career URL may not contain "
            "ASCII control characters"
        )

    try:
        parsed = urlsplit(
            value
        )
    except ValueError as exc:
        raise ATSIdentificationError(
            "career URL is structurally invalid"
        ) from exc

    if parsed.scheme != "https":
        raise ATSIdentificationError(
            "career URL must use https"
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ATSIdentificationError(
            "career URL may not contain credentials"
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise ATSIdentificationError(
            "career URL port invalid"
        ) from exc

    if port not in {
        None,
        443,
    }:
        raise ATSIdentificationError(
            "career URL may not use "
            "non-default port"
        )

    host = parsed.hostname

    if not host:
        raise ATSIdentificationError(
            "career URL requires hostname"
        )

    host = host.casefold()

    normalized_input = urlunsplit(
        (
            "https",
            host,
            parsed.path or "",
            "",
            "",
        )
    )

    return (
        normalized_input,
        parsed,
        host,
    )


def _segments(
    parsed: SplitResult,
) -> tuple[str, ...]:

    return tuple(
        segment
        for segment in parsed.path.split("/")
        if segment
    )


def _opaque(
    value: str,
) -> str | None:

    if "%" in value:
        return None

    if not _OPAQUE_SEGMENT_RE.fullmatch(
        value
    ):
        return None

    return value


def _provider_only(
    *,
    input_url: str,
    provider_kind: str,
) -> ATSIdentificationResult:

    return ATSIdentificationResult(
        input_url=input_url,
        status=
            ATSIdentificationStatus
            .ATS_IDENTIFIED,
        provider_kind=provider_kind,
    )


def _unrecognized(
    input_url: str,
) -> ATSIdentificationResult:

    return ATSIdentificationResult(
        input_url=input_url,
        status=
            ATSIdentificationStatus
            .UNRECOGNIZED,
    )


def _endpoint(
    *,
    input_url: str,
    provider_kind: str,
    identity: dict[str, str],
    canonical_career_url: str,
) -> ATSIdentificationResult:

    canonical = (
        canonicalize_provider_identity(
            provider_kind,
            identity,
        )
    )

    return ATSIdentificationResult(
        input_url=input_url,
        status=
            ATSIdentificationStatus
            .ENDPOINT_IDENTIFIED,

        provider_kind=
            canonical.provider_kind,

        canonical_career_url=
            canonical_career_url,

        provider_identity_key=
            canonical.provider_identity_key,

        provider_identity_json=
            canonical.canonical_json,

        provider_identity_sha256=
            canonical.identity_sha256,
    )


def _identify_greenhouse(
    *,
    input_url: str,
    parsed: SplitResult,
    host: str,
) -> ATSIdentificationResult:

    segments = _segments(parsed)

    if not segments:
        return _provider_only(
            input_url=input_url,
            provider_kind="greenhouse",
        )

    board = _opaque(
        segments[0]
    )

    if board is None:
        return _provider_only(
            input_url=input_url,
            provider_kind="greenhouse",
        )

    return _endpoint(
        input_url=input_url,
        provider_kind="greenhouse",
        identity={
            "host": host,
            "board_token": board,
        },
        canonical_career_url=(
            f"https://{host}/{board}"
        ),
    )


def _identify_lever(
    *,
    input_url: str,
    parsed: SplitResult,
) -> ATSIdentificationResult:

    segments = _segments(parsed)

    if not segments:
        return _provider_only(
            input_url=input_url,
            provider_kind="lever",
        )

    site = _opaque(
        segments[0]
    )

    if site is None:
        return _provider_only(
            input_url=input_url,
            provider_kind="lever",
        )

    return _endpoint(
        input_url=input_url,
        provider_kind="lever",
        identity={
            "host": _LEVER_HOST,
            "site": site,
        },
        canonical_career_url=(
            f"https://{_LEVER_HOST}/{site}"
        ),
    )


def _identify_ashby(
    *,
    input_url: str,
    parsed: SplitResult,
) -> ATSIdentificationResult:

    segments = _segments(parsed)

    if not segments:
        return _provider_only(
            input_url=input_url,
            provider_kind="ashby",
        )

    board = _opaque(
        segments[0]
    )

    if board is None:
        return _provider_only(
            input_url=input_url,
            provider_kind="ashby",
        )

    return _endpoint(
        input_url=input_url,
        provider_kind="ashby",
        identity={
            "host": _ASHBY_HOST,
            "board": board,
        },
        canonical_career_url=(
            f"https://{_ASHBY_HOST}/{board}"
        ),
    )


def _smart_company_from_api_path(
    segments: tuple[str, ...],
) -> str | None:

    candidates = []

    if (
        len(segments) >= 3
        and segments[0].casefold()
        == "v1"
        and segments[1].casefold()
        == "companies"
    ):
        candidates.append(
            segments[2]
        )

    if (
        len(segments) >= 2
        and segments[0].casefold()
        == "companies"
    ):
        candidates.append(
            segments[1]
        )

    for candidate in candidates:

        normalized = _opaque(
            candidate
        )

        if normalized is not None:
            return normalized

    return None


def _identify_smartrecruiters(
    *,
    input_url: str,
    parsed: SplitResult,
    host: str,
) -> ATSIdentificationResult:

    segments = _segments(parsed)

    company = None

    if host in _SMART_PUBLIC_HOSTS:

        if segments:
            company = _opaque(
                segments[0]
            )

    elif host == _SMART_API_HOST:

        company = (
            _smart_company_from_api_path(
                segments
            )
        )

    if company is None:

        return _provider_only(
            input_url=input_url,
            provider_kind=
                "smartrecruiters",
        )

    return _endpoint(
        input_url=input_url,
        provider_kind=
            "smartrecruiters",

        identity={
            "host":
                _SMART_API_HOST,

            "company_identifier":
                company,
        },

        canonical_career_url=(
            "https://"
            "careers.smartrecruiters.com/"
            f"{company}"
        ),
    )


def _identify_workday(
    *,
    input_url: str,
    parsed: SplitResult,
    host: str,
    tenant: str,
) -> ATSIdentificationResult:

    segments = _segments(parsed)

    if not segments:
        return _provider_only(
            input_url=input_url,
            provider_kind="workday",
        )

    if (
        segments[0].casefold()
        == "wday"
    ):
        return _provider_only(
            input_url=input_url,
            provider_kind="workday",
        )

    site = None
    canonical_path = None

    if _LOCALE_RE.fullmatch(
        segments[0]
    ):

        if len(segments) < 2:
            return _provider_only(
                input_url=input_url,
                provider_kind="workday",
            )

        locale = segments[0]

        site = _opaque(
            segments[1]
        )

        if site is not None:
            canonical_path = (
                f"/{locale}/{site}"
            )

    else:

        site = _opaque(
            segments[0]
        )

        if site is not None:
            canonical_path = (
                f"/{site}"
            )

    if (
        site is None
        or canonical_path is None
    ):

        return _provider_only(
            input_url=input_url,
            provider_kind="workday",
        )

    return _endpoint(
        input_url=input_url,
        provider_kind="workday",

        identity={
            "host": host,
            "tenant": tenant,
            "site": site,
        },

        canonical_career_url=(
            f"https://{host}"
            f"{canonical_path}"
        ),
    )


def identify_career_url(
    career_url: str,
) -> ATSIdentificationResult:
    """Identify supported ATS endpoint from a known URL.

    This function is deliberately offline.  It does
    not follow redirects, resolve DNS, fetch content,
    probe endpoints, or infer custom domains.
    """

    (
        input_url,
        parsed,
        host,
    ) = _validated_url(
        career_url
    )

    if host in _GREENHOUSE_HOSTS:

        return _identify_greenhouse(
            input_url=input_url,
            parsed=parsed,
            host=host,
        )

    if host == _LEVER_HOST:

        return _identify_lever(
            input_url=input_url,
            parsed=parsed,
        )

    if host == _ASHBY_HOST:

        return _identify_ashby(
            input_url=input_url,
            parsed=parsed,
        )

    if (
        host in _SMART_PUBLIC_HOSTS
        or host == _SMART_API_HOST
    ):

        return _identify_smartrecruiters(
            input_url=input_url,
            parsed=parsed,
            host=host,
        )

    workday_match = (
        _WORKDAY_HOST_RE.fullmatch(
            host
        )
    )

    if workday_match is not None:

        return _identify_workday(
            input_url=input_url,
            parsed=parsed,
            host=host,
            tenant=
                workday_match.group(
                    "tenant"
                ),
        )

    return _unrecognized(
        input_url
    )
