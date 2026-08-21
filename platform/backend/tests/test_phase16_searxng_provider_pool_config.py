from __future__ import annotations

from pathlib import Path
import re


EXPECTED_PROVIDER_POOL = (
    "bing",
    "wiby",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _settings_text() -> str:
    path = (
        _repository_root()
        / "deploy"
        / "phase12h-searxng"
        / "settings.yml"
    )

    return path.read_text(
        encoding="utf-8"
    )


def _extract_keep_only(
    text: str,
) -> tuple[str, ...]:
    lines = text.splitlines()

    for index, line in enumerate(lines):

        if line != "    keep_only:":
            continue

        values: list[str] = []

        for candidate in lines[index + 1:]:

            if candidate.startswith(
                "      - "
            ):
                values.append(
                    candidate.removeprefix(
                        "      - "
                    ).strip()
                )
                continue

            if candidate.strip() == "":
                continue

            break

        return tuple(values)

    raise AssertionError(
        "SearXNG keep_only block missing"
    )


def _extract_engine_blocks(
    text: str,
) -> dict[str, str]:
    match = re.search(
        r"(?m)^engines:\s*$",
        text,
    )

    assert match is not None, (
        "top-level SearXNG engines block missing"
    )

    tail = text[match.end():]

    next_top = re.search(
        r"(?m)"
        r"^[A-Za-z0-9_]"
        r"[A-Za-z0-9_-]*:\s*",
        tail,
    )

    section = (
        tail[:next_top.start()]
        if next_top
        else tail
    )

    block_pattern = re.compile(
        r"(?ms)"
        r"^  - name:\s*"
        r"([^\n#]+?)\s*$"
        r"(.*?)"
        r"(?=^  - name:|\Z)"
    )

    blocks: dict[str, str] = {}

    for block in block_pattern.finditer(
        section
    ):

        name = block.group(1).strip(
            "'\" "
        )

        assert name not in blocks, (
            f"duplicate SearXNG engine block: "
            f"{name}"
        )

        blocks[name] = block.group(0)

    return blocks


def test_phase16_searxng_provider_pool_is_exactly_qualified_pool() -> None:
    text = _settings_text()

    keep_only = _extract_keep_only(
        text
    )

    blocks = _extract_engine_blocks(
        text
    )

    assert keep_only == (
        EXPECTED_PROVIDER_POOL
    )

    assert tuple(blocks) == (
        EXPECTED_PROVIDER_POOL
    )

    assert set(keep_only) == set(
        blocks
    )


def test_phase16_searxng_provider_pool_activation_is_explicit() -> None:
    blocks = _extract_engine_blocks(
        _settings_text()
    )

    for engine in (
        EXPECTED_PROVIDER_POOL
    ):

        block = blocks[engine]

        assert re.search(
            r"(?m)^    inactive: false\s*$",
            block,
        ), (
            f"{engine} must explicitly set "
            "inactive: false so SearXNG "
            "upstream defaults cannot silently "
            "remove it from the effective "
            "runtime registry"
        )

        assert re.search(
            r"(?m)^    disabled: false\s*$",
            block,
        ), (
            f"{engine} must explicitly set "
            "disabled: false"
        )


def test_phase16_searxng_rejected_engines_are_not_in_provider_pool() -> None:
    text = _settings_text()

    keep_only = set(
        _extract_keep_only(text)
    )

    blocks = set(
        _extract_engine_blocks(text)
    )

    rejected = {
        "google",
        "qwant",
        "mojeek",
        "wikipedia",
        "yahoo",
    }

    assert keep_only.isdisjoint(
        rejected
    )

    assert blocks.isdisjoint(
        rejected
    )
