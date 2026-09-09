import asyncio
import json

import httpx

from agents.registry import agent_registry
from agents.router import agent_router
from agents.schemas import AgentRunRequest
from gateway.aws_knowledge import (
    AWSKnowledgeLiteClient,
    MAX_EVIDENCE_CHARS,
)
from tools.aws_research import AWSResearchTool
from tools.registry import tool_registry


def test_devops_agent_advertises_aws_research() -> None:
    agent = agent_registry.get("devops-agent")

    assert "aws.research" in agent.tools


def test_aws_research_tool_is_registered() -> None:
    tool = tool_registry.get("aws.research")

    assert tool.definition.id == "aws.research"
    assert tool.definition.safe is True
    assert tool.definition.requires_confirmation is False


def test_smart_router_routes_aws_to_devops() -> None:
    route = agent_router.route(
        AgentRunRequest(
            mode="smart",
            objective=(
                "Explain Amazon VPC networking "
                "and NAT Gateway behavior"
            ),
        )
    )

    assert route.agent_id == "devops-agent"


def test_aws_knowledge_normal_question_is_one_call() -> None:
    calls: list[str] = []

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        search_phrase = (
            payload["params"]
            ["arguments"]
            ["search_phrase"]
        )

        calls.append(
            search_phrase
        )

        assert (
            request.headers[
                "mcp-protocol-version"
            ]
            == "2026-07-28"
        )

        assert (
            request.headers["mcp-name"]
            == "aws___search_documentation"
        )

        return httpx.Response(
            200,
            headers={
                "content-type": (
                    "application/json"
                ),
            },
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "structuredContent": {
                        "content": {
                            "result": [
                                {
                                    "rank_order": 1,
                                    "title": (
                                        "AWS Direct Connect"
                                    ),
                                    "url": (
                                        "https://docs.aws.amazon.com/"
                                        "directconnect/latest/"
                                        "UserGuide/Welcome.html"
                                    ),
                                    "context": (
                                        "AWS Direct Connect "
                                        "provides dedicated "
                                        "network connectivity."
                                    ),
                                }
                            ]
                        }
                    },
                    "content": [],
                },
            },
        )

    async def run() -> None:
        client = AWSKnowledgeLiteClient(
            endpoint=(
                "https://example.test/mcp"
            ),
            transport=httpx.MockTransport(
                handler
            ),
        )

        result = await client.research(
            "What is AWS Direct Connect used for?"
        )

        assert (
            result["search_count"]
            == 1
        )

        assert result["cached"] is False

        assert len(
            result["evidence"]
        ) <= MAX_EVIDENCE_CHARS

        assert (
            "AWS Direct Connect"
            in result["evidence"]
        )

        assert len(calls) == 1

        cached = await client.research(
            "What is AWS Direct Connect used for?"
        )

        assert cached["cached"] is True
        assert len(calls) == 1

    asyncio.run(run())


def test_aws_comparison_uses_two_targeted_searches() -> None:
    calls: list[str] = []

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        search_phrase = (
            payload["params"]
            ["arguments"]
            ["search_phrase"]
        )

        calls.append(
            search_phrase
        )

        lower = search_phrase.lower()

        if "internet gateway" in lower:
            records = [
                {
                    "rank_order": 1,
                    "title": (
                        "AWS Certification article"
                    ),
                    "url": (
                        "https://aws.amazon.com/"
                        "blogs/training-and-certification/"
                        "example/"
                    ),
                    "context": (
                        "Training material."
                    ),
                },
                {
                    "rank_order": 2,
                    "title": (
                        "Internet gateways"
                    ),
                    "url": (
                        "https://docs.aws.amazon.com/"
                        "vpc/latest/userguide/"
                        "VPC_Internet_Gateway.html"
                    ),
                    "context": (
                        "An internet gateway "
                        "is attached to a VPC."
                    ),
                },
            ]

        elif "nat gateway" in lower:
            records = [
                {
                    "rank_order": 1,
                    "title": "NAT gateways",
                    "url": (
                        "https://docs.aws.amazon.com/"
                        "vpc/latest/userguide/"
                        "vpc-nat-gateway.html"
                    ),
                    "context": (
                        "AWS supports public "
                        "and private NAT gateways."
                    ),
                }
            ]

        else:
            raise AssertionError(
                "unexpected comparison query: "
                + search_phrase
            )

        return httpx.Response(
            200,
            headers={
                "content-type": (
                    "application/json"
                ),
            },
            json={
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "structuredContent": {
                        "content": {
                            "result": records
                        }
                    },
                    "content": [],
                },
            },
        )

    question = (
        "Compare an AWS Internet Gateway "
        "and NAT Gateway for the AWS "
        "certification exam. Include placement, "
        "routing, IP addressing, inbound/outbound "
        "behavior, IPv6 considerations, and cite "
        "official AWS documentation."
    )

    async def run() -> None:
        client = AWSKnowledgeLiteClient(
            endpoint=(
                "https://example.test/mcp"
            ),
            transport=httpx.MockTransport(
                handler
            ),
        )

        result = await client.research(
            question
        )

        assert (
            result["search_count"]
            == 2
        )

        assert len(calls) == 2

        for search_phrase in calls:
            assert (
                "certification"
                not in search_phrase.lower()
            )

            assert (
                "exam"
                not in search_phrase.lower()
            )

        assert (
            "Internet gateways"
            in result["evidence"]
        )

        assert (
            "NAT gateways"
            in result["evidence"]
        )

        assert (
            len(result["evidence"])
            <= MAX_EVIDENCE_CHARS
        )

        assert (
            result["sources"][0]
            == (
                "https://docs.aws.amazon.com/"
                "vpc/latest/userguide/"
                "VPC_Internet_Gateway.html"
            )
        )

        assert (
            (
                "https://docs.aws.amazon.com/"
                "vpc/latest/userguide/"
                "vpc-nat-gateway.html"
            )
            in result["sources"]
        )

        cached = await client.research(
            question
        )

        assert cached["cached"] is True

        # Cache prevents another two
        # upstream searches.
        assert len(calls) == 2

    asyncio.run(run())


def test_aws_research_tool_rejects_empty_question() -> None:
    async def run() -> None:
        tool = AWSResearchTool()

        result = await tool.execute(
            {"question": "   "}
        )

        assert result.success is False
        assert result.error is not None

    asyncio.run(run())


def test_canonical_vpc_guide_beats_secondary_docs() -> None:
    records = [
        {
            "rank_order": 1,
            "title": "NAT64 architecture",
            "url": (
                "https://docs.aws.amazon.com/"
                "reference-architecture-diagrams/"
                "latest/ipv6-vpc-architectures/"
                "ipv6-nat64.html"
            ),
        },
        {
            "rank_order": 2,
            "title": "Designing DNS for IPv6",
            "url": (
                "https://docs.aws.amazon.com/"
                "whitepapers/latest/"
                "ipv6-on-aws/"
                "designing-dns-for-ipv6.html"
            ),
        },
        {
            "rank_order": 3,
            "title": "NAT gateways",
            "url": (
                "https://docs.aws.amazon.com/"
                "vpc/latest/userguide/"
                "vpc-nat-gateway.html"
            ),
        },
        {
            "rank_order": 4,
            "title": "NAT64 and DNS64",
            "url": (
                "https://docs.aws.amazon.com/"
                "vpc/latest/userguide/"
                "nat-gateway-nat64-dns64.html"
            ),
        },
    ]

    ranked = sorted(
        records,
        key=(
            AWSKnowledgeLiteClient
            ._record_priority
        ),
    )

    assert (
        ranked[0]["url"]
        == (
            "https://docs.aws.amazon.com/"
            "vpc/latest/userguide/"
            "vpc-nat-gateway.html"
        )
    )

    assert (
        ranked[1]["url"]
        == (
            "https://docs.aws.amazon.com/"
            "vpc/latest/userguide/"
            "nat-gateway-nat64-dns64.html"
        )
    )


def test_nat_comparison_query_prefers_core_nat_docs() -> None:
    question = (
        "Compare an AWS Internet Gateway "
        "and NAT Gateway for the AWS certification "
        "exam. Include placement, routing, "
        "IP addressing, inbound/outbound behavior, "
        "IPv6 considerations, and cite official "
        "AWS documentation."
    )

    queries = (
        AWSKnowledgeLiteClient
        ._plan_searches(question)
    )

    assert len(queries) == 2

    nat_query = queries[1].lower()

    assert "public nat gateway" in nat_query
    assert "private nat gateway" in nat_query
    assert "elastic ip" in nat_query

    # These terms previously biased AWS Knowledge
    # away from the canonical NAT Gateway guide.
    assert "nat64" not in nat_query
    assert "internet gateway" not in nat_query

    assert "certification" not in nat_query
    assert "exam" not in nat_query
