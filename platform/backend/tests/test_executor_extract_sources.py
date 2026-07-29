from agents.executor import AgentExecutor


def test_extract_sources_from_sources():
    executor = AgentExecutor()

    result = executor._extract_sources(
        {
            "sources": [
                {"id": 1},
                {"id": 2},
            ]
        }
    )

    assert result == [
        {"id": 1},
        {"id": 2},
    ]


def test_extract_sources_from_results():
    executor = AgentExecutor()

    result = executor._extract_sources(
        {
            "results": [
                {"name": "doc"},
            ]
        }
    )

    assert result == [
        {"name": "doc"},
    ]


def test_extract_sources_nested_data():
    executor = AgentExecutor()

    result = executor._extract_sources(
        {
            "data": {
                "documents": [
                    {"title": "paper"},
                ]
            }
        }
    )

    assert result == [
        {"title": "paper"},
    ]


def test_extract_sources_none():
    executor = AgentExecutor()

    result = executor._extract_sources({})

    assert result == []
