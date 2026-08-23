from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, Literal, cast
from unittest.mock import patch

from agents.cancellation import raise_if_current_cancellation_requested
from gateway import internet_transport as transport
from gateway import research_retrieval_latency_probe_e2 as e2
from gateway.internet_transport import ConnectionFactory

PHASE16_GZIP_EXPERIMENT_VERSION: Literal["phase16f1.1"] = "phase16f1.1"
EXPERIMENT_TRANSPORT_ID = "dap-pinned-https-http1-gzip-shadow-v1"
BASELINE_FROZEN_RETRIEVAL_SOURCE_P95_MS = 1698.145


class _GzipPinnedHTTPSFetcher(transport.PinnedHTTPSFetcher):
    """Diagnostic-only gzip-capable variant of the sealed pinned HTTPS fetcher."""

    gzip_response_count = 0
    identity_response_count = 0

    @staticmethod
    def _build_request(admission: Any) -> bytes:
        request = transport.PinnedHTTPSFetcher._build_request(admission)
        marker = b"Accept-Encoding: identity\r\n"
        replacement = b"Accept-Encoding: gzip, identity\r\n"
        if request.count(marker) != 1:
            raise transport.InternetTransportError(
                "gzip-experiment-request-contract-mismatch",
                "Sealed transport request no longer has the expected identity encoding marker.",
            )
        return request.replace(marker, replacement, 1)

    async def _read_response(
        self,
        reader: asyncio.StreamReader,
        method: Literal["GET", "HEAD"],
    ) -> transport._ParsedHTTPResponse:
        try:
            raw_headers = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=self._limits.read_timeout_seconds,
            )
        except asyncio.LimitOverrunError as exc:
            raise transport.InternetTransportError(
                "response-headers-too-large",
                "Response headers exceeded the sealed byte ceiling.",
            ) from exc
        except asyncio.IncompleteReadError as exc:
            raise transport.InternetTransportError(
                "response-headers-incomplete",
                "Connection closed before response headers completed.",
            ) from exc
        except TimeoutError as exc:
            raise transport.InternetTransportError(
                "response-header-timeout",
                "Timed out waiting for response headers.",
            ) from exc

        if len(raw_headers) > self._limits.max_header_bytes:
            raise transport.InternetTransportError(
                "response-headers-too-large",
                "Response headers exceeded the sealed byte ceiling.",
            )

        status_code, reason, headers = self._parse_headers(raw_headers)
        content_type = self._content_type(headers)
        content_length = self._content_length(headers)
        transfer_encoding = self._single_header(headers, "transfer-encoding")
        content_encoding = self._single_header(headers, "content-encoding")
        location = self._single_header(headers, "location")
        normalized_encoding = (content_encoding or "identity").strip().lower()

        if normalized_encoding not in {"identity", "gzip"}:
            raise transport.InternetTransportError(
                "content-encoding-unsupported",
                "Phase 16F.1 shadow transport accepts only identity or gzip encoding.",
            )
        if transfer_encoding and transfer_encoding.lower() != "chunked":
            raise transport.InternetTransportError(
                "response-transfer-encoding-unsupported",
                "Only identity or chunked HTTP transfer framing is supported.",
            )
        if transfer_encoding and content_length is not None:
            raise transport.InternetTransportError(
                "response-framing-ambiguous",
                "Response contains both Transfer-Encoding and Content-Length.",
            )

        is_redirect = status_code in transport._REDIRECT_STATUS_CODES
        if is_redirect:
            if location is None or not location.strip():
                raise transport.InternetTransportError(
                    "response-redirect-location-missing",
                    "Redirect response did not provide a usable Location header.",
                )
            return transport._ParsedHTTPResponse(
                status_code=status_code,
                reason=reason,
                content_type=content_type,
                content_length=content_length,
                body=b"",
                redirect_location=location.strip(),
                etag=self._single_header(headers, "etag"),
                last_modified=self._single_header(headers, "last-modified"),
            )

        if (
            method != "HEAD"
            and status_code not in transport._NO_BODY_STATUS_CODES
            and content_type not in self._limits.allowed_content_types
        ):
            raise transport.InternetTransportError(
                "content-type-unsupported",
                "Response Content-Type is outside the sealed research allowlist.",
            )

        if method == "HEAD" or status_code in transport._NO_BODY_STATUS_CODES:
            wire_body = b""
        elif transfer_encoding and transfer_encoding.lower() == "chunked":
            wire_body = await self._read_chunked_body(reader)
        elif content_length is not None:
            if content_length > self._limits.max_body_bytes:
                raise transport.InternetTransportError(
                    "content-body-too-large",
                    "Wire Content-Length exceeds the sealed body ceiling.",
                )
            wire_body = await self._read_exact(reader, content_length)
        else:
            wire_body = await self._read_to_eof(reader)

        if normalized_encoding == "gzip" and wire_body:
            body = _decode_gzip_bounded(wire_body, self._limits.max_body_bytes)
            type(self).gzip_response_count += 1
        else:
            body = wire_body
            type(self).identity_response_count += 1

        raise_if_current_cancellation_requested(boundary="after-internet-response-read")
        return transport._ParsedHTTPResponse(
            status_code=status_code,
            reason=reason,
            content_type=content_type,
            content_length=content_length,
            body=body,
            redirect_location=None,
            etag=self._single_header(headers, "etag"),
            last_modified=self._single_header(headers, "last-modified"),
        )


def _decode_gzip_bounded(payload: bytes, max_decoded_bytes: int) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        decoded = decoder.decompress(payload, max_decoded_bytes + 1)
        if len(decoded) > max_decoded_bytes or decoder.unconsumed_tail:
            raise transport.InternetTransportError(
                "content-body-too-large",
                "Decoded gzip body exceeds the sealed body ceiling.",
            )
        remaining = max_decoded_bytes + 1 - len(decoded)
        decoded += decoder.flush(remaining)
    except zlib.error as exc:
        raise transport.InternetTransportError(
            "content-encoding-invalid",
            "Gzip response failed bounded validation.",
        ) from exc

    if len(decoded) > max_decoded_bytes:
        raise transport.InternetTransportError(
            "content-body-too-large",
            "Decoded gzip body exceeds the sealed body ceiling.",
        )
    if not decoder.eof or decoder.unused_data:
        raise transport.InternetTransportError(
            "content-encoding-invalid",
            "Gzip response is incomplete or contains unsupported trailing members.",
        )
    return decoded


class _GzipTimedFetcher(e2._TimedFetcher):
    def __init__(
        self,
        accumulator: e2._TimingAccumulator,
        timer: e2.TimerProvider,
    ) -> None:
        connection_factory = e2._TimedConnectionFactory(accumulator, timer)
        self._delegate = _GzipPinnedHTTPSFetcher(
            connection_factory=cast(ConnectionFactory, connection_factory)
        )
        self._accumulator = accumulator
        self._timer = timer


async def run_phase16f1_gzip_experiment(
    *,
    source_commit: str,
    truth_db: Path,
) -> dict[str, Any]:
    _GzipPinnedHTTPSFetcher.gzip_response_count = 0
    _GzipPinnedHTTPSFetcher.identity_response_count = 0
    with patch.object(e2, "_TimedFetcher", _GzipTimedFetcher):
        detail_report = await e2.run_phase16e2_latency_probe(
            source_commit=source_commit,
            truth_db=truth_db,
        )

    gzip_p95 = detail_report.frozen_retrieval_source_p95_ms
    delta = (
        None
        if gzip_p95 is None
        else round(gzip_p95 - BASELINE_FROZEN_RETRIEVAL_SOURCE_P95_MS, 3)
    )
    limits = transport.InternetTransportLimits()
    payload: dict[str, Any] = {
        "experiment_version": PHASE16_GZIP_EXPERIMENT_VERSION,
        "experimental_transport_id": EXPERIMENT_TRANSPORT_ID,
        "source_commit": source_commit,
        "corpus_version": detail_report.corpus_version,
        "provider_id": detail_report.provider_id,
        "case_count": detail_report.case_count,
        "successful_case_count": detail_report.successful_case_count,
        "baseline_frozen_retrieval_source_p95_ms": (
            BASELINE_FROZEN_RETRIEVAL_SOURCE_P95_MS
        ),
        "gzip_frozen_retrieval_source_p50_ms": (
            detail_report.frozen_retrieval_source_p50_ms
        ),
        "gzip_frozen_retrieval_source_p95_ms": gzip_p95,
        "gzip_vs_baseline_p95_delta_ms": delta,
        "frozen_retrieval_source_target_ms": (
            detail_report.frozen_retrieval_source_target_ms
        ),
        "meets_frozen_retrieval_source_target": (
            detail_report.meets_frozen_retrieval_source_target
        ),
        "gzip_response_count": _GzipPinnedHTTPSFetcher.gzip_response_count,
        "identity_response_count": _GzipPinnedHTTPSFetcher.identity_response_count,
        "wire_body_ceiling_bytes": limits.max_body_bytes,
        "decoded_body_ceiling_bytes": limits.max_body_bytes,
        "accepted_content_encodings": ["identity", "gzip"],
        "production_transport_mutated": False,
        "production_transport_id": transport.TRANSPORT_ID,
        "transport_timeout_mutated": False,
        "retry_policy_mutated": False,
        "concurrency_policy_mutated": False,
        "provider_configuration_mutated": False,
        "production_truth_mutation_performed": False,
        "smart_routing_research_activated": False,
        "provider_switching_performed": False,
        "generic_network_authority_expanded": False,
        "guardian_contacted": False,
        "privileged_host_action_performed": False,
        "detail_report": detail_report.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["report_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_report(payload: dict[str, Any], path: Path) -> None:
    resolved = path.expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def _async_main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--truth-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = await run_phase16f1_gzip_experiment(
        source_commit=args.source_commit,
        truth_db=args.truth_db,
    )
    write_report(payload, args.output)
    print(f"phase16f1_experiment_version|{payload['experiment_version']}")
    print(f"phase16f1_successful_cases|{payload['successful_case_count']}/30")
    print(f"phase16f1_gzip_response_count|{payload['gzip_response_count']}")
    print(f"phase16f1_identity_response_count|{payload['identity_response_count']}")
    print(
        "phase16f1_baseline_frozen_p95_ms|"
        f"{payload['baseline_frozen_retrieval_source_p95_ms']}"
    )
    print(
        "phase16f1_gzip_frozen_p95_ms|"
        f"{payload['gzip_frozen_retrieval_source_p95_ms']}"
    )
    print(
        "phase16f1_gzip_p95_delta_ms|"
        f"{payload['gzip_vs_baseline_p95_delta_ms']}"
    )
    print(
        "phase16f1_frozen_target|"
        + ("PASS" if payload["meets_frozen_retrieval_source_target"] else "FAIL")
    )
    print(f"phase16f1_report_sha256|{payload['report_sha256']}")
    print("PHASE16_GZIP_SHADOW_EXPERIMENT|PASS")
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
