from datetime import datetime

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    status: str
    document: DocumentInfo


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total: int


class DocumentDeleteResponse(BaseModel):
    status: str
    document_id: str
    deleted_chunks: int


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=4000,
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )
    score_threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    document_id: str | None = None


class SearchResult(BaseModel):
    score: float
    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int
    text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


class KnowledgeHealthResponse(BaseModel):
    status: str
    qdrant_online: bool
    ollama_online: bool
    embedding_model: str
    collection: str


class SourceCitation(BaseModel):
    citation_id: str
    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int
    score: float
    excerpt: str


class AskRequest(BaseModel):
    question: str = Field(
        min_length=2,
        max_length=4000,
    )

    model: str | None = None

    provider: str = Field(
        default="auto",
        pattern="^(auto|ollama)$",
    )

    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
    )

    max_tokens: int = Field(
        default=600,
        ge=1,
        le=8192,
    )

    retrieval_limit: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    score_threshold: float | None = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
    )

    document_id: str | None = None


class RagUsageMetrics(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float


class AskResponse(BaseModel):
    answer: str
    provider: str
    model: str
    sources: list[SourceCitation]
    usage: RagUsageMetrics
