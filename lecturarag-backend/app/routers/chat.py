"""RAG chat endpoints."""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import ChatMessage
from app.schemas import (
    ChatHistoryResponse,
    ChatMessageRead,
    ChatRequest,
    ChatResponse,
    Citation,
    SourceChunk,
)
from app.services.document_service import get_document, load_document_index
from app.services.llm_service import LLMService, get_llm_service
from app.services.rag_engine import retrieve

router = APIRouter(prefix="/api/chat", tags=["chat"])

_CITATION_MARKER = re.compile(r"\[Page \d+\]")


def _snippet(text: str, limit: int = 240) -> str:
    compressed = re.sub(r"\s+", " ", text).strip()
    if len(compressed) <= limit:
        return compressed
    cut = compressed.rfind(" ", 0, limit - 3)
    if cut < limit // 2:
        cut = limit - 3
    return compressed[:cut].rstrip() + "..."


def _parse_citations(raw: str) -> list[Citation]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    citations: list[Citation] = []
    for item in parsed if isinstance(parsed, list) else []:
        try:
            citations.append(Citation.model_validate(item, strict=False))
        except Exception:  # noqa: BLE001 - tolerate legacy rows
            continue
    return citations


@router.post("", response_model=ChatResponse, summary="Ask a question about a document")
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm: LLMService = Depends(get_llm_service),
) -> ChatResponse:
    document = get_document(db, payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    index = load_document_index(db, document.id)
    if not index:
        raise HTTPException(status_code=409, detail="This document has no indexed text.")

    top_k = payload.top_k or settings.retrieval_top_k
    retrieved = retrieve(
        index,
        payload.message,
        top_k=top_k,
        dimensions=settings.embedding_dimensions,
    )
    if not retrieved:
        raise HTTPException(status_code=422, detail="Could not retrieve any relevant passages.")

    user_message = ChatMessage(
        document_id=document.id,
        role="user",
        content=payload.message,
        citations="[]",
        model="input",
        fallback_used=False,
    )
    db.add(user_message)
    db.commit()

    generated = await llm.answer(payload.message, retrieved)

    citations = [
        Citation(
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            similarity=chunk.similarity,
            snippet=_snippet(chunk.content),
        )
        for chunk in retrieved
    ]
    sources = [
        SourceChunk(
            page_number=chunk.page_number,
            chunk_index=chunk.chunk_index,
            similarity=chunk.similarity,
            content=chunk.content,
        )
        for chunk in retrieved
    ]

    answer = generated.text.strip()
    if citations and generated.grounded and not _CITATION_MARKER.search(answer):
        pages = ", ".join(f"[Page {chunk.page_number}]" for chunk in retrieved)
        answer = f"{answer}\n\nSources: {pages}"

    assistant_message = ChatMessage(
        document_id=document.id,
        role="assistant",
        content=answer,
        citations=json.dumps([citation.model_dump() for citation in citations]),
        model=generated.model,
        fallback_used=generated.fallback_used,
    )
    db.add(assistant_message)
    db.commit()

    return ChatResponse(
        message_id=assistant_message.id,
        document_id=document.id,
        answer=answer,
        citations=citations,
        sources=sources,
        model=generated.model,
        fallback_used=generated.fallback_used,
        created_at=assistant_message.created_at,
    )


@router.get(
    "/{document_id}/history",
    response_model=ChatHistoryResponse,
    summary="Read the chat transcript for a document",
)
def chat_history(
    document_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    statement = (
        select(ChatMessage)
        .where(ChatMessage.document_id == document_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    messages = list(db.scalars(statement).all())
    return ChatHistoryResponse(
        document_id=document_id,
        messages=[
            ChatMessageRead(
                id=message.id,
                role=message.role,  # type: ignore[arg-type]
                content=message.content,
                citations=_parse_citations(message.citations),
                model=message.model,
                fallback_used=message.fallback_used,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )
