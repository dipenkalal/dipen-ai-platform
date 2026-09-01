from __future__ import annotations

import hashlib
import json
from typing import Any


WORKDAY_CXS_PAGE_SIZE = 20

WORKDAY_CXS_MAX_OFFSET = 2000

WORKDAY_CXS_MAX_SEARCH_CHARS = 120

WORKDAY_CXS_MAX_REQUEST_BYTES = 4096


class WorkdayCXSRequestError(
    ValueError
):
    """
    Fail-closed bounded Workday CXS
    request-contract error.
    """


def _normalize_search_text(
    value: str,
) -> str:

    if not isinstance(
        value,
        str,
    ):
        raise WorkdayCXSRequestError(
            "Workday searchText must be a string."
        )

    normalized = " ".join(
        value.split()
    )

    if (
        len(normalized)
        > WORKDAY_CXS_MAX_SEARCH_CHARS
    ):
        raise WorkdayCXSRequestError(
            "Workday searchText exceeds "
            "the bounded length."
        )

    if any(
        ord(char) < 0x20
        for char in normalized
    ):
        raise WorkdayCXSRequestError(
            "Workday searchText contains "
            "control characters."
        )

    return normalized


def build_workday_cxs_jobs_body(
    *,
    offset: int = 0,
    search_text: str = "",
) -> bytes:

    if (
        not isinstance(
            offset,
            int,
        )
        or isinstance(
            offset,
            bool,
        )
    ):
        raise WorkdayCXSRequestError(
            "Workday offset must be an integer."
        )

    if (
        offset < 0
        or offset
        > WORKDAY_CXS_MAX_OFFSET
        or offset
        % WORKDAY_CXS_PAGE_SIZE
        != 0
    ):
        raise WorkdayCXSRequestError(
            "Workday offset must be a "
            "bounded multiple of 20."
        )

    normalized_search = (
        _normalize_search_text(
            search_text
        )
    )

    payload = {
        "appliedFacets": {},
        "limit":
            WORKDAY_CXS_PAGE_SIZE,
        "offset":
            offset,
        "searchText":
            normalized_search,
    }

    body = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    if (
        len(body)
        > WORKDAY_CXS_MAX_REQUEST_BYTES
    ):
        raise WorkdayCXSRequestError(
            "Workday request body exceeds "
            "the byte ceiling."
        )

    return body


def validate_workday_cxs_jobs_body(
    body: bytes,
) -> str:

    if not isinstance(
        body,
        bytes,
    ):
        raise WorkdayCXSRequestError(
            "Workday request body must be bytes."
        )

    if (
        not body
        or len(body)
        > WORKDAY_CXS_MAX_REQUEST_BYTES
    ):
        raise WorkdayCXSRequestError(
            "Workday request body violates "
            "the byte ceiling."
        )

    try:

        decoded = body.decode(
            "utf-8"
        )

        payload: Any = json.loads(
            decoded
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:

        raise WorkdayCXSRequestError(
            "Workday request body must be "
            "valid UTF-8 JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise WorkdayCXSRequestError(
            "Workday request root must "
            "be an object."
        )

    if set(payload) != {
        "appliedFacets",
        "limit",
        "offset",
        "searchText",
    }:
        raise WorkdayCXSRequestError(
            "Workday request contains "
            "unsupported fields."
        )

    if (
        payload[
            "appliedFacets"
        ]
        != {}
    ):
        raise WorkdayCXSRequestError(
            "Workday appliedFacets must "
            "remain empty."
        )

    if (
        payload[
            "limit"
        ]
        != WORKDAY_CXS_PAGE_SIZE
    ):
        raise WorkdayCXSRequestError(
            "Workday page size must "
            "remain exactly 20."
        )

    expected = (
        build_workday_cxs_jobs_body(
            offset=payload[
                "offset"
            ],
            search_text=payload[
                "searchText"
            ],
        )
    )

    if body != expected:
        raise WorkdayCXSRequestError(
            "Workday request body is "
            "not canonical JSON."
        )

    return hashlib.sha256(
        body
    ).hexdigest()
