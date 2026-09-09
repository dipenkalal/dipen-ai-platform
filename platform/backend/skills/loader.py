from pathlib import Path
import re


_SKILLS_ROOT = Path(__file__).resolve().parent
_SAFE_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


def load_skill(name: str) -> str:
    normalized = name.strip().lower()

    if not _SAFE_SKILL_NAME.fullmatch(normalized):
        raise ValueError(f"Invalid skill name: {name!r}")

    path = _SKILLS_ROOT / normalized / "SKILL.md"

    if not path.is_file():
        raise FileNotFoundError(
            f"DAP skill was not found: {normalized}"
        )

    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(
            f"DAP skill is empty: {normalized}"
        )

    return content
