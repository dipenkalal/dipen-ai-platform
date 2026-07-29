import pytest
from knowledge.services.chunker import (
    TextChunk,
    chunk_text,
    normalize_whitespace,
)


def test_normalize_whitespace_removes_extra_spaces():
    text = "Hello     world\n\nThis   is   a   test"

    result = normalize_whitespace(text)

    assert result == "Hello world\n\nThis is a test"


def test_normalize_whitespace_removes_blank_lines():
    text = "\n\nOne\n\n\nTwo\n\n"

    result = normalize_whitespace(text)

    assert result == "One\n\nTwo"


def test_chunk_text_invalid_chunk_size():
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("abc", 0, 0)


def test_chunk_text_negative_overlap():
    with pytest.raises(ValueError, match="overlap cannot"):
        chunk_text("abc", 10, -1)


def test_chunk_text_overlap_too_large():
    with pytest.raises(ValueError, match="overlap must"):
        chunk_text("abc", 10, 10)


def test_chunk_text_empty_after_normalization():
    assert chunk_text(" \n \n ", 50, 5) == []


def test_chunk_text_single_chunk():
    chunks = chunk_text(
        "This is a simple sentence.",
        chunk_size=100,
        overlap=10,
    )

    assert len(chunks) == 1
    assert chunks[0] == TextChunk(
        index=0,
        text="This is a simple sentence.",
    )


def test_chunk_text_multiple_chunks():
    text = "Sentence one. Sentence two. Sentence three. Sentence four."

    chunks = chunk_text(
        text,
        chunk_size=25,
        overlap=5,
    )

    assert len(chunks) >= 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1


def test_chunk_text_with_overlap():
    text = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    chunks = chunk_text(
        text,
        chunk_size=20,
        overlap=5,
    )

    assert len(chunks) >= 3

    for i, chunk in enumerate(chunks):
        assert chunk.index == i
        assert chunk.text


def test_chunk_text_breaks_after_sentence_before_long_word():
    text = "Alpha beta gamma. Supercalifragilisticexpialidocious"

    chunks = chunk_text(
        text,
        chunk_size=25,
        overlap=0,
    )

    assert len(chunks) >= 2
    assert chunks[0] == TextChunk(
        index=0,
        text="Alpha beta gamma.",
    )
