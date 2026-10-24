"""Pydantic v2 schemas.

API-facing models are strict (`strict=True`, `extra="forbid"`) so malformed
payloads are rejected instead of silently coerced. The structured-output
drafts an LLM returns live here too; they share the same shape but are
validated with `strict=False` because providers often emit `"3"` for `3`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Difficulty = Literal["easy", "medium", "hard"]
CardStatus = Literal["new", "needs_review", "mastered"]
ChatRole = Literal["user", "assistant"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class OrmModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
        str_strip_whitespace=True,
    )


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #
class DocumentRead(OrmModel):
    id: str
    filename: str
    title: str
    file_type: Literal["pdf", "markdown"]
    page_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    char_count: int = Field(ge=0)
    created_at: datetime


class DocumentUploadResponse(StrictModel):
    document: DocumentRead
    message: str


class DocumentListResponse(StrictModel):
    documents: list[DocumentRead]
    total: int = Field(ge=0)


# --------------------------------------------------------------------------- #
# Chat / RAG
# --------------------------------------------------------------------------- #
class Citation(StrictModel):
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    similarity: float = Field(ge=0.0, le=1.0)
    snippet: str


class SourceChunk(StrictModel):
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    similarity: float = Field(ge=0.0, le=1.0)
    content: str


class ChatRequest(StrictModel):
    document_id: str = Field(min_length=1, max_length=36)
    message: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


class ChatResponse(StrictModel):
    message_id: str
    document_id: str
    answer: str
    citations: list[Citation]
    sources: list[SourceChunk]
    model: str
    fallback_used: bool
    created_at: datetime


class ChatMessageRead(OrmModel):
    id: str
    role: ChatRole
    content: str
    citations: list[Citation]
    model: str
    fallback_used: bool
    created_at: datetime


class ChatHistoryResponse(StrictModel):
    document_id: str
    messages: list[ChatMessageRead]


# --------------------------------------------------------------------------- #
# Flashcards
# --------------------------------------------------------------------------- #
class FlashcardDraft(StrictModel):
    """One generated card (also the LLM structured-output contract)."""

    front: str = Field(min_length=3, max_length=400)
    back: str = Field(min_length=3, max_length=1200)
    source_page: int = Field(ge=1)
    difficulty: Difficulty


class FlashcardGenerateRequest(StrictModel):
    document_id: str = Field(min_length=1, max_length=36)
    count: int = Field(default=12, ge=5, le=20)


class FlashcardRead(OrmModel):
    id: str
    order_index: int = Field(ge=0)
    front: str
    back: str
    source_page: int = Field(ge=1)
    difficulty: Difficulty
    status: CardStatus


class DeckRead(OrmModel):
    id: str
    document_id: str
    title: str
    model: str
    fallback_used: bool
    created_at: datetime
    cards: list[FlashcardRead]


class FlashcardDeckListResponse(StrictModel):
    document_id: str
    decks: list[DeckRead]


class FlashcardStatusUpdate(StrictModel):
    status: CardStatus


# --------------------------------------------------------------------------- #
# Quizzes
# --------------------------------------------------------------------------- #
class QuizQuestionDraft(StrictModel):
    """One generated question (also the LLM structured-output contract)."""

    question: str = Field(min_length=8, max_length=600)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=3, max_length=1500)
    source_page: int = Field(ge=1)


class QuizGenerateRequest(StrictModel):
    document_id: str = Field(min_length=1, max_length=36)
    num_questions: int = Field(default=6, ge=3, le=15)


class QuizQuestionRead(OrmModel):
    """Question as shown before answering; the answer key stays server-side."""

    id: str
    order_index: int = Field(ge=0)
    question: str
    options: list[str]
    source_page: int = Field(ge=1)


class QuizRead(OrmModel):
    id: str
    document_id: str
    title: str
    model: str
    fallback_used: bool
    created_at: datetime
    questions: list[QuizQuestionRead]


class QuizListResponse(StrictModel):
    document_id: str
    quizzes: list[QuizRead]


class QuizAttemptRequest(StrictModel):
    quiz_id: str = Field(min_length=1, max_length=36)
    answers: list[int | None] = Field(min_length=1, max_length=50)


class QuizAnswerCheckRequest(StrictModel):
    quiz_id: str = Field(min_length=1, max_length=36)
    question_id: str = Field(min_length=1, max_length=36)
    selected_index: int | None = Field(default=None, ge=0, le=3)


class QuizAnswerCheckResponse(StrictModel):
    question_id: str
    selected_index: int | None
    correct_index: int = Field(ge=0, le=3)
    is_correct: bool
    explanation: str
    source_page: int = Field(ge=1)


class QuizQuestionResult(StrictModel):
    question_id: str
    order_index: int = Field(ge=0)
    question: str
    options: list[str]
    selected_index: int | None
    correct_index: int = Field(ge=0, le=3)
    is_correct: bool
    explanation: str
    source_page: int = Field(ge=1)


class QuizAttemptResponse(StrictModel):
    attempt_id: str
    quiz_id: str
    score: int = Field(ge=0)
    total: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0)
    results: list[QuizQuestionResult]
    created_at: datetime


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #
class HealthResponse(StrictModel):
    status: Literal["ok"]
    app: str
    version: str
    llm_mode: Literal["openai-compatible", "deterministic-fallback"]
    database: str


class ErrorResponse(StrictModel):
    detail: str
