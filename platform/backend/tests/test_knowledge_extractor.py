from types import SimpleNamespace

import knowledge.services.extractor as extractor
import pytest


def test_extract_pdf_text_collects_non_empty_pages(
    monkeypatch,
    tmp_path,
):
    pdf_path = tmp_path / "sample.pdf"

    pages = [
        SimpleNamespace(extract_text=lambda: " First page text "),
        SimpleNamespace(extract_text=lambda: None),
        SimpleNamespace(extract_text=lambda: "   "),
        SimpleNamespace(extract_text=lambda: "Second page text"),
    ]

    class FakePdfReader:
        def __init__(self, path):
            assert path == str(pdf_path)
            self.pages = pages

    monkeypatch.setattr(
        extractor,
        "PdfReader",
        FakePdfReader,
    )

    result = extractor.extract_pdf_text(pdf_path)

    assert result == (
        "[Page 1]\nFirst page text\n\n[Page 4]\nSecond page text"
    )


def test_extract_pdf_text_handles_no_pages(
    monkeypatch,
    tmp_path,
):
    pdf_path = tmp_path / "empty.pdf"

    class FakePdfReader:
        def __init__(self, path):
            self.pages = []

    monkeypatch.setattr(
        extractor,
        "PdfReader",
        FakePdfReader,
    )

    assert extractor.extract_pdf_text(pdf_path) == ""


def test_extract_plain_text_reads_utf8(
    tmp_path,
):
    file_path = tmp_path / "document.txt"
    file_path.write_text(
        "Hello UTF-8 ✓",
        encoding="utf-8",
    )

    result = extractor.extract_plain_text(file_path)

    assert result == "Hello UTF-8 ✓"


def test_extract_plain_text_falls_back_to_latin1(
    tmp_path,
):
    file_path = tmp_path / "document.txt"
    file_path.write_bytes("café".encode("latin-1"))

    result = extractor.extract_plain_text(file_path)

    assert result == "café"


@pytest.mark.parametrize(
    "extension",
    [
        ".txt",
        ".md",
        ".markdown",
    ],
)
def test_extract_document_text_uses_plain_text(
    monkeypatch,
    tmp_path,
    extension,
):
    file_path = tmp_path / f"document{extension}"

    calls = []

    def fake_extract_plain_text(path):
        calls.append(path)
        return "Line one   \nLine two\t  \n"

    monkeypatch.setattr(
        extractor,
        "extract_plain_text",
        fake_extract_plain_text,
    )

    result = extractor.extract_document_text(file_path)

    assert result == "Line one\nLine two"
    assert calls == [file_path]


def test_extract_document_text_uses_pdf_extractor(
    monkeypatch,
    tmp_path,
):
    file_path = tmp_path / "document.PDF"

    calls = []

    def fake_extract_pdf_text(path):
        calls.append(path)
        return "[Page 1]\nPDF text   \n"

    monkeypatch.setattr(
        extractor,
        "extract_pdf_text",
        fake_extract_pdf_text,
    )

    result = extractor.extract_document_text(file_path)

    assert result == "[Page 1]\nPDF text"
    assert calls == [file_path]


def test_extract_document_text_rejects_unsupported_extension(
    tmp_path,
):
    file_path = tmp_path / "document.docx"

    with pytest.raises(
        extractor.UnsupportedDocumentError,
        match=r"Unsupported file extension: \.docx",
    ):
        extractor.extract_document_text(file_path)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "\n\n",
        "  \n\t\n  ",
    ],
)
def test_extract_document_text_rejects_empty_text(
    monkeypatch,
    tmp_path,
    text,
):
    file_path = tmp_path / "empty.txt"

    monkeypatch.setattr(
        extractor,
        "extract_plain_text",
        lambda path: text,
    )

    with pytest.raises(
        extractor.EmptyDocumentError,
        match="contains no extractable text",
    ):
        extractor.extract_document_text(file_path)


def test_extract_document_text_normalizes_trailing_whitespace(
    monkeypatch,
    tmp_path,
):
    file_path = tmp_path / "notes.md"

    monkeypatch.setattr(
        extractor,
        "extract_plain_text",
        lambda path: "Heading\nContent with spaces\n\nFinal line\t\t",
    )

    result = extractor.extract_document_text(file_path)

    assert result == ("Heading\nContent with spaces\n\nFinal line")


def test_custom_exceptions_are_value_errors():
    assert issubclass(
        extractor.UnsupportedDocumentError,
        ValueError,
    )
    assert issubclass(
        extractor.EmptyDocumentError,
        ValueError,
    )
