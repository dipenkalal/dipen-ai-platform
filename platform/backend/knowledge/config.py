import os
from pathlib import Path

KNOWLEDGE_UPLOAD_DIRECTORY = Path(
    os.getenv(
        "KNOWLEDGE_UPLOAD_DIRECTORY",
        "/home/dipen/dap/data/knowledge/uploads",
    )
)

KNOWLEDGE_UPLOAD_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://127.0.0.1:6333",
).rstrip("/")


QDRANT_COLLECTION = os.getenv(
    "QDRANT_COLLECTION",
    "dap_knowledge",
)


OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434",
).rstrip("/")


OLLAMA_EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "embeddinggemma",
)


MAX_FILE_SIZE_BYTES = int(
    os.getenv(
        "KNOWLEDGE_MAX_FILE_SIZE_BYTES",
        str(25 * 1024 * 1024),
    )
)


DEFAULT_CHUNK_SIZE = int(
    os.getenv(
        "KNOWLEDGE_CHUNK_SIZE",
        "900",
    )
)


DEFAULT_CHUNK_OVERLAP = int(
    os.getenv(
        "KNOWLEDGE_CHUNK_OVERLAP",
        "150",
    )
)


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".markdown",
}
