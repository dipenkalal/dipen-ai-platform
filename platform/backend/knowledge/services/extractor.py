from pathlib import Path

from pypdf import PdfReader


class UnsupportedDocumentError(ValueError):
    pass


class EmptyDocumentError(ValueError):
    pass


def extract_pdf_text(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    page_texts: list[str] = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        extracted = page.extract_text() or ""
        cleaned = extracted.strip()

        if cleaned:
            page_texts.append(
                f"[Page {page_number}]\n{cleaned}"
            )

    return "\n\n".join(page_texts)


def extract_plain_text(file_path: Path) -> str:
    try:
        return file_path.read_text(
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        return file_path.read_text(
            encoding="latin-1",
        )


def extract_document_text(
    file_path: Path,
) -> str:
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        text = extract_pdf_text(file_path)
    elif extension in {
        ".txt",
        ".md",
        ".markdown",
    }:
        text = extract_plain_text(file_path)
    else:
        raise UnsupportedDocumentError(
            f"Unsupported file extension: {extension}"
        )

    normalized = "\n".join(
        line.rstrip()
        for line in text.splitlines()
    ).strip()

    if not normalized:
        raise EmptyDocumentError(
            "The uploaded document contains no extractable text."
        )

    return normalized
