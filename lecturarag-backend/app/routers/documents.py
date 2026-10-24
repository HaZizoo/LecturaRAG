"""Document upload and management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Document
from app.schemas import (
    DocumentListResponse,
    DocumentRead,
    DocumentUploadResponse,
)
from app.services.document_service import delete_document, get_document, ingest_document
from app.services.rag_engine import detect_file_type, sanitize_filename

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a PDF or Markdown lecture",
)
def upload_document(
    file: UploadFile = File(..., description="PDF or Markdown lecture file"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    filename = sanitize_filename(file.filename or "")
    try:
        detect_file_type(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = file.file.read(settings.max_upload_bytes + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
        )

    try:
        document = ingest_document(db, filename, payload, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(document),
        message=(
            f"Indexed {document.chunk_count} chunks across {document.page_count} pages."
        ),
    )


@router.get("", response_model=DocumentListResponse, summary="List indexed documents")
def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    total = db.scalar(select(func.count()).select_from(Document)) or 0
    statement = (
        select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    )
    documents = list(db.scalars(statement).all())
    return DocumentListResponse(
        documents=[DocumentRead.model_validate(document) for document in documents],
        total=int(total),
    )


@router.get("/{document_id}", response_model=DocumentRead, summary="Get a document")
def read_document(document_id: str, db: Session = Depends(get_db)) -> DocumentRead:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentRead.model_validate(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its generated study material",
)
def remove_document(document_id: str, db: Session = Depends(get_db)) -> Response:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_document(db, document)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
