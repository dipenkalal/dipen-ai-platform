from dataclasses import dataclass


@dataclass(slots=True)
class TextChunk:
    index: int
    text: str


def normalize_whitespace(text: str) -> str:
    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in text.split("\n")
        if paragraph.strip()
    ]

    return "\n\n".join(paragraphs)


def chunk_text(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    normalized = normalize_whitespace(text)

    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    text_length = len(normalized)

    while start < text_length:
        target_end = min(
            start + chunk_size,
            text_length,
        )

        end = target_end

        if target_end < text_length:
            candidate_breaks = [
                normalized.rfind(
                    "\n\n",
                    start,
                    target_end,
                ),
                normalized.rfind(
                    ". ",
                    start,
                    target_end,
                ),
                normalized.rfind(
                    " ",
                    start,
                    target_end,
                ),
            ]

            best_break = max(candidate_breaks)

            if best_break > start + (chunk_size // 2):
                end = best_break + 1

        chunk_content = normalized[start:end].strip()

        if chunk_content:
            chunks.append(
                TextChunk(
                    index=index,
                    text=chunk_content,
                )
            )
            index += 1

        if end >= text_length:
            break

        start = max(
            end - overlap,
            start + 1,
        )

    return chunks
