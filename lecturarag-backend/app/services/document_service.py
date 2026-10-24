"""Document ingestion and lookup helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Chunk, Document
from app.services.rag_engine import IndexedChunk, load_index, prepare_document, serialize_embedding


def get_document(db: Session, document_id: str) -> Document | None:
    return db.get(Document, document_id)


def load_chunks(db: Session, document_id: str) -> list[Chunk]:
    statement = (
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    return list(db.scalars(statement).all())


def load_document_index(db: Session, document_id: str) -> list[IndexedChunk]:
    return load_index(load_chunks(db, document_id))


def ingest_document(
    db: Session,
    filename: str,
    data: bytes,
    *,
    settings: Settings | None = None,
    title_override: str | None = None,
) -> Document:
    """Parse, chunk, embed and persist an uploaded lecture."""

    config = settings or get_settings()
    prepared = prepare_document(filename, data, settings=config, title_override=title_override)

    document = Document(
        filename=prepared.filename,
        title=prepared.title,
        file_type=prepared.file_type,
        page_count=len(prepared.pages),
        chunk_count=len(prepared.chunks),
        char_count=prepared.char_count,
    )
    db.add(document)
    db.flush()

    for chunk in prepared.chunks:
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                char_count=len(chunk.content),
                embedding=serialize_embedding(chunk.embedding),
            )
        )

    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
