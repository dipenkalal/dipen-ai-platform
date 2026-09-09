from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx


AWS_KNOWLEDGE_MCP_ENDPOINT = os.getenv(
    "AWS_KNOWLEDGE_MCP_ENDPOINT",
    "https://knowledge-mcp.global.api.aws",
).strip()

AWS_KNOWLEDGE_PROTOCOL_VERSION = "2026-07-28"
AWS_SEARCH_TOOL = "aws___search_documentation"

MAX_RESULTS = 4
MAX_RESULT_CHARS = 850
MAX_EVIDENCE_CHARS = 4800
MAX_QUERY_CHARS = 700
MAX_QUERY_WORDS = 80
CACHE_TTL_SECONDS = 600.0

MAX_SEARCHES = 2

_COMPARISON_RE = re.compile(
    r"(?i)\b(?:"
    r"compare|comparison|versus|vs\.?|"
    r"difference|differences|differ"
    r")\b"
)

_PRESENTATION_NOISE_RE = re.compile(
    r"(?i)\b(?:"
    r"aws certification|"
    r"certification exam|"
    r"certification|"
    r"exam|"
    r"study|studying|"
    r"quiz|quizzes|"
    r"exam tips?"
    r")\b"
)

_AWS_SEARCH_SUBJECTS = (
    (
        re.compile(
            r"(?i)\binternet\s+gateway\b"
        ),
        (
            "Amazon VPC Internet Gateway routing "
            "public IPv4 IPv6 public subnet"
        ),
    ),
    (
        re.compile(
            r"(?i)\bnat\s+gateway\b"
        ),
        (
            "Amazon VPC NAT gateways public NAT gateway "
            "private NAT gateway Elastic IP"
        ),
    ),
    (
        re.compile(
            r"(?i)\bdirect\s+connect\b"
        ),
        (
            "AWS Direct Connect dedicated network "
            "connectivity virtual interfaces"
        ),
    ),
    (
        re.compile(
            r"(?i)\bapplication\s+load\s+balancer\b"
        ),
        (
            "Elastic Load Balancing "
            "Application Load Balancer"
        ),
    ),
    (
        re.compile(
            r"(?i)\bnetwork\s+load\s+balancer\b"
        ),
        (
            "Elastic Load Balancing "
            "Network Load Balancer"
        ),
    ),
    (
        re.compile(
            r"(?i)\broute\s*53\b"
        ),
        "Amazon Route 53 DNS routing",
    ),
    (
        re.compile(
            r"(?i)\bcloudformation\b"
        ),
        "AWS CloudFormation documentation",
    ),
    (
        re.compile(
            r"(?i)\bdynamodb\b"
        ),
        "Amazon DynamoDB documentation",
    ),
    (
        re.compile(
            r"(?i)\brds\b"
        ),
        "Amazon RDS documentation",
    ),
)


_AWS_URL_RE = re.compile(
    r"https://(?:"
    r"docs\.aws\.amazon\.com|"
    r"aws\.amazon\.com|"
    r"repost\.aws|"
    r"docs\.amplify\.aws|"
    r"ui\.docs\.amplify\.aws"
    r")[^\s\]\)>\"']+",
    re.IGNORECASE,
)

_AWS_OBJECTIVE_RE = re.compile(
    r"(?i)(?:"
    r"\baws\b|"
    r"amazon web services|"
    r"\bec2\b|"
    r"\bs3\b|"
    r"\bvpc\b|"
    r"\brds\b|"
    r"route\s*53|"
    r"cloudformation|"
    r"cloudwatch|"
    r"dynamodb|"
    r"direct connect|"
    r"nat gateway|"
    r"internet gateway|"
    r"application load balancer|"
    r"network load balancer|"
    r"\beks\b|"
    r"\becs\b"
    r")"
)


class AWSKnowledgeError(RuntimeError):
    """Raised when bounded AWS Knowledge retrieval fails."""


def is_aws_question(value: str) -> bool:
    return bool(_AWS_OBJECTIVE_RE.search(value or ""))


class AWSKnowledgeLiteClient:
    """
    Bounded, read-only AWS Knowledge MCP client.

    The model never receives direct MCP access. DAP performs exactly one
    search_documentation call and gives the model a compact evidence bundle.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = (
            endpoint or AWS_KNOWLEDGE_MCP_ENDPOINT
        ).rstrip("/")
        self.transport = transport
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=20.0,
            write=20.0,
            pool=10.0,
        )
        self._cache: dict[
            str,
            tuple[float, dict[str, Any]],
        ] = {}

    @staticmethod
    def _normalize_question(question: str) -> str:
        normalized = " ".join(question.split())

        if not normalized:
            raise ValueError(
                "AWS research question must not be empty"
            )

        words = normalized.split()[:MAX_QUERY_WORDS]
        normalized = " ".join(words)

        if len(normalized) > MAX_QUERY_CHARS:
            normalized = normalized[:MAX_QUERY_CHARS].rsplit(
                " ",
                1,
            )[0]

        return normalized

    @staticmethod
    def _decode_sse(text: str) -> dict[str, Any]:
        data_lines: list[str] = []

        for line in text.splitlines():
            if line.startswith("data:"):
                data_lines.append(
                    line[len("data:"):].strip()
                )

            if not line.strip() and data_lines:
                candidate = "\n".join(data_lines)
                data_lines = []

                try:
                    payload = json.loads(candidate)
                except json.JSONDecodeError:
                    continue

                if isinstance(payload, dict) and (
                    "result" in payload
                    or "error" in payload
                ):
                    return payload

        if data_lines:
            try:
                payload = json.loads(
                    "\n".join(data_lines)
                )
            except json.JSONDecodeError:
                payload = None

            if isinstance(payload, dict):
                return payload

        raise AWSKnowledgeError(
            "AWS Knowledge returned an unreadable SSE response"
        )

    @classmethod
    def _decode_response(
        cls,
        response: httpx.Response,
    ) -> dict[str, Any]:
        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if "application/json" in content_type:
            payload = response.json()
            if not isinstance(payload, dict):
                raise AWSKnowledgeError(
                    "AWS Knowledge returned invalid JSON"
                )
            return payload

        if "text/event-stream" in content_type:
            return cls._decode_sse(response.text)

        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError):
            return cls._decode_sse(response.text)

        if not isinstance(payload, dict):
            raise AWSKnowledgeError(
                "AWS Knowledge returned an invalid response"
            )

        return payload

    @staticmethod
    def _collect_records(
        value: Any,
        records: list[dict[str, Any]],
    ) -> None:
        if isinstance(value, list):
            for item in value:
                AWSKnowledgeLiteClient._collect_records(
                    item,
                    records,
                )
            return

        if not isinstance(value, dict):
            return

        if any(
            key in value
            for key in (
                "url",
                "context",
                "snippet",
                "title",
                "rank_order",
            )
        ):
            records.append(value)

        for key in (
            "results",
            "items",
            "documents",
            "result",
            "content",
            "structuredContent",
            "structured_content",
        ):
            nested = value.get(key)
            if nested is not None:
                AWSKnowledgeLiteClient._collect_records(
                    nested,
                    records,
                )

    @staticmethod
    def _unique_urls(text: str) -> list[str]:
        urls: list[str] = []

        for match in _AWS_URL_RE.findall(text):
            url = match.rstrip(".,;:")

            if url not in urls:
                urls.append(url)

            if len(urls) >= 8:
                break

        return urls

    @classmethod
    def _plan_searches(
        cls,
        question: str,
    ) -> list[str]:
        normalized = cls._normalize_question(
            question
        )

        subjects: list[str] = []

        for pattern, search_phrase in (
            _AWS_SEARCH_SUBJECTS
        ):
            if pattern.search(normalized):
                if search_phrase not in subjects:
                    subjects.append(
                        search_phrase
                    )

        technical_question = normalized

        # Exam/study wording is presentation intent when
        # the question already names AWS technical subjects.
        # Keep such wording intact for genuine questions
        # about AWS Certification itself.
        if subjects:
            technical_question = (
                _PRESENTATION_NOISE_RE.sub(
                    " ",
                    technical_question,
                )
            )

            technical_question = " ".join(
                technical_question.split()
            ).strip(
                " ,.;:-"
            )

        # A comparison naming multiple known AWS components
        # gets at most one technical search per component.
        if (
            _COMPARISON_RE.search(normalized)
            and len(subjects) >= 2
        ):
            return subjects[:MAX_SEARCHES]

        return [
            technical_question or normalized
        ]

    @staticmethod
    def _record_priority(
        record: dict[str, Any],
    ) -> tuple[int, int, str]:
        url = str(
            record.get("url") or ""
        ).lower()

        title = str(
            record.get("title") or ""
        ).lower()

        # Prefer canonical AWS service user guides.
        #
        # AWS Knowledge may rank tutorials, CDK API docs,
        # whitepapers, reference architectures or re:Post
        # above the core service documentation. For DAP's
        # certification/study path, canonical service docs
        # must win when they are available.

        canonical_core_paths = (
            (
                "/vpc/latest/userguide/"
                "vpc_internet_gateway.html"
            ),
            (
                "/vpc/latest/userguide/"
                "vpc-nat-gateway.html"
            ),
        )

        canonical_supporting_paths = (
            (
                "/vpc/latest/userguide/"
                "nat-gateway-nat64-dns64.html"
            ),
        )

        if (
            "docs.aws.amazon.com" in url
            and any(
                path_value in url
                for path_value
                in canonical_core_paths
            )
        ):
            tier = -20

        elif (
            "docs.aws.amazon.com" in url
            and any(
                path_value in url
                for path_value
                in canonical_supporting_paths
            )
        ):
            tier = -10

        elif (
            "docs.aws.amazon.com" in url
            and "/latest/userguide/" in url
        ):
            tier = 0

        elif (
            "docs.aws.amazon.com" in url
            and "/userguide/" in url
        ):
            tier = 1

        elif "docs.aws.amazon.com" in url:
            tier = 2

        elif (
            "aws.amazon.com" in url
            and "/blogs/" not in url
        ):
            tier = 3

        elif "repost.aws" in url:
            tier = 4

        else:
            tier = 5

        # Secondary documentation is useful supporting
        # evidence, but should not displace the canonical
        # service guide when evidence space is bounded.

        if "/cdk/api/" in url:
            tier += 5

        if "/whitepapers/" in url:
            tier += 4

        if (
            "/reference-architecture-diagrams/"
            in url
        ):
            tier += 3

        if "/blogs/" in url:
            tier += 5

        if (
            "aws-certification" in url
            or
            "training-and-certification" in url
            or
            "certification" in title
            or
            "exam guide" in title
        ):
            tier += 10

        raw_rank = record.get(
            "rank_order"
        )

        try:
            rank = int(raw_rank)
        except (
            TypeError,
            ValueError,
        ):
            rank = 999

        return (
            tier,
            rank,
            title,
        )

    @classmethod
    def _compact_result(
        cls,
        result: dict[str, Any],
        max_chars: int = MAX_EVIDENCE_CHARS,
    ) -> tuple[str, list[str]]:
        if result.get("isError") is True:
            raise AWSKnowledgeError(
                "AWS Knowledge tool reported an error"
            )

        structured = (
            result.get("structuredContent")
            or result.get("structured_content")
        )

        content = result.get("content")
        text_blocks: list[str] = []

        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    text_blocks.append(text.strip())

        candidates: list[Any] = []

        if structured is not None:
            candidates.append(structured)

        for block in text_blocks:
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError:
                continue

            candidates.append(parsed)

        records: list[dict[str, Any]] = []

        for candidate in candidates:
            cls._collect_records(
                candidate,
                records,
            )

        body_parts: list[str] = []
        source_urls: list[str] = []

        if records:
            ranked_records = sorted(
                records,
                key=cls._record_priority,
            )

            deduped_records: list[
                dict[str, Any]
            ] = []

            seen_records: set[str] = set()

            for record in ranked_records:
                url_key = str(
                    record.get("url") or ""
                ).strip().lower()

                title_key = str(
                    record.get("title") or ""
                ).strip().lower()

                key = (
                    url_key
                    or title_key
                )

                if not key:
                    key = repr(record)

                if key in seen_records:
                    continue

                seen_records.add(key)
                deduped_records.append(
                    record
                )

            for index, record in enumerate(
                deduped_records[:MAX_RESULTS],
                start=1,
            ):
                title = str(
                    record.get("title") or "AWS documentation"
                ).strip()

                url = str(
                    record.get("url") or ""
                ).strip()

                context = str(
                    record.get("context")
                    or record.get("snippet")
                    or record.get("text")
                    or ""
                ).strip()

                context = context[:MAX_RESULT_CHARS]

                section = [f"[{index}] {title}"]

                if url:
                    section.append(f"Source: {url}")
                    if url not in source_urls:
                        source_urls.append(url)

                if context:
                    section.append(
                        f"Evidence: {context}"
                    )

                body_parts.append("\n".join(section))

        else:
            raw = "\n\n".join(text_blocks).strip()

            if not raw and structured is not None:
                raw = json.dumps(
                    structured,
                    ensure_ascii=False,
                    default=str,
                )

            if not raw:
                raise AWSKnowledgeError(
                    "AWS Knowledge returned no usable evidence"
                )

            body_parts.append(raw)

        raw_for_urls = "\n".join(body_parts)

        for url in cls._unique_urls(raw_for_urls):
            if url not in source_urls:
                source_urls.append(url)

        source_urls = source_urls[:8]

        header = (
            "AWS KNOWLEDGE LITE — OFFICIAL AWS EVIDENCE\n\n"
            "Use only the evidence below for AWS-specific factual claims.\n"
            "Do not invent unsupported requirements, defaults, quotas, "
            "prices, permissions, or networking behavior.\n\n"
        )

        sources_block = ""

        if source_urls:
            sources_block = (
                "\n\nAWS source URLs:\n"
                + "\n".join(
                    f"- {url}"
                    for url in source_urls
                )
            )

        body = "\n\n".join(body_parts).strip()

        available = (
            max_chars
            - len(header)
            - len(sources_block)
        )

        if available < 200:
            available = 200

        body = body[:available].rstrip()

        evidence = (
            header
            + body
            + sources_block
        )[:max_chars]

        return evidence, source_urls

    async def _search_once(
        self,
        search_phrase: str,
        search_number: int,
    ) -> dict[str, Any]:
        request_id = (
            f"dap-aws-search-{search_number}"
        )

        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": AWS_SEARCH_TOOL,
                "arguments": {
                    "search_phrase": (
                        search_phrase
                    ),
                    "limit": MAX_RESULTS,
                    "topics": ["general"],
                },
                "_meta": {
                    "io.modelcontextprotocol/clientInfo": {
                        "name": (
                            "dap-aws-knowledge-lite"
                        ),
                        "version": "1.0.0",
                    }
                },
            },
        }

        headers = {
            "accept": (
                "application/json, "
                "text/event-stream"
            ),
            "content-type": (
                "application/json"
            ),
            "mcp-protocol-version": (
                AWS_KNOWLEDGE_PROTOCOL_VERSION
            ),
            "mcp-method": "tools/call",
            "mcp-name": AWS_SEARCH_TOOL,
            "user-agent": (
                "dipen-ai-platform/"
                "aws-knowledge-lite-v1"
            ),
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()

        except httpx.HTTPError as exc:
            raise AWSKnowledgeError(
                "AWS Knowledge request failed: "
                f"{exc}"
            ) from exc

        rpc = self._decode_response(
            response
        )

        if rpc.get("error") is not None:
            error = rpc["error"]

            if isinstance(error, dict):
                message = str(
                    error.get("message")
                    or "unknown MCP error"
                )
            else:
                message = str(error)

            raise AWSKnowledgeError(
                "AWS Knowledge MCP error: "
                f"{message}"
            )

        result = rpc.get("result")

        if not isinstance(result, dict):
            raise AWSKnowledgeError(
                "AWS Knowledge response did "
                "not contain a tool result"
            )

        return result

    async def research(
        self,
        question: str,
    ) -> dict[str, Any]:
        normalized_question = (
            self._normalize_question(
                question
            )
        )

        search_phrases = (
            self._plan_searches(
                normalized_question
            )
        )[:MAX_SEARCHES]

        cache_key = "\x1f".join(
            search_phrases
        )

        cached = self._cache.get(
            cache_key
        )

        now = time.monotonic()

        if cached is not None:
            cached_at, cached_value = cached

            if (
                now - cached_at
                <= CACHE_TTL_SECONDS
            ):
                return {
                    **cached_value,
                    "cached": True,
                }

        results: list[
            dict[str, Any]
        ] = []

        for index, search_phrase in enumerate(
            search_phrases,
            start=1,
        ):
            result = await self._search_once(
                search_phrase,
                index,
            )

            results.append(
                result
            )

        if not results:
            raise AWSKnowledgeError(
                "AWS Knowledge planner produced "
                "no search result"
            )

        if len(results) == 1:
            per_search_budget = (
                MAX_EVIDENCE_CHARS
            )
        else:
            per_search_budget = (
                MAX_EVIDENCE_CHARS
                // len(results)
            )

        evidence_parts: list[str] = []
        source_urls: list[str] = []

        for result in results:
            evidence_part, sources = (
                self._compact_result(
                    result,
                    max_chars=(
                        per_search_budget
                    ),
                )
            )

            evidence_parts.append(
                evidence_part
            )

            for source in sources:
                if source not in source_urls:
                    source_urls.append(
                        source
                    )

        evidence = "\n\n".join(
            evidence_parts
        )[:MAX_EVIDENCE_CHARS]

        source_urls = source_urls[:8]

        value = {
            "query": normalized_question,
            "queries": search_phrases,
            "evidence": evidence,
            "sources": source_urls,
            "search_count": len(
                search_phrases
            ),
            "characters": len(
                evidence
            ),
            "cached": False,
            "provider": (
                "aws-knowledge-mcp"
            ),
            "tool": AWS_SEARCH_TOOL,
        }

        self._cache[cache_key] = (
            now,
            value,
        )

        return value
