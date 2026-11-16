"""FastAPI RAG pipeline tests that never call external services."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tempfile.gettempdir()) / 'lecturarag-pytest.db').as_posix()}"
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["LLM_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Base, SessionLocal, engine, init_db
from app.main import app
from app.models import Chunk, Document
from app.services.document_service import ingest_document
from app.services.llm_service import LLMService, get_llm_service
from app.services.rag_engine import ParsedPage, PreparedDocument, TextChunk, prepare_document


@pytest.fixture()
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    init_db()
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    client.close()
    app.dependency_overrides.clear()


def test_pdf_upload_uses_mocked_processing(client: TestClient) -> None:
    prepared = PreparedDocument(
        filename="lecture.pdf",
        title="Mocked PDF",
        file_type="pdf",
        pages=[ParsedPage(page_number=1, text="Mocked PDF content.")],
        chunks=[
            TextChunk(
                chunk_index=0,
                page_number=1,
                content="Mocked PDF content.",
                embedding=[0.0, 1.0],
            )
        ],
    )
    with patch("app.services.document_service.prepare_document", return_value=prepared) as process:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("lecture.pdf", b"%PDF-mocked", "application/pdf")},
        )

    assert response.status_code == 201
    assert response.json()["document"]["file_type"] == "pdf"
    process.assert_called_once()


def test_embedding_is_mocked() -> None:
    settings = Settings(chunk_size=200, chunk_overlap=0, embedding_dimensions=128)
    with patch("app.services.rag_engine.embed_text", return_value=[0.0, 1.0]) as embed:
        prepared = prepare_document(
            "lecture.md",
            b"# Lecture\n\nNeural networks learn useful patterns from examples.",
            settings=settings,
        )

    assert prepared.chunks[0].embedding == [0.0, 1.0]
    embed.assert_called_once()


def test_offline_llm_failure_uses_deterministic_fallback(client: TestClient) -> None:
    with SessionLocal() as db:
        document = Document(
            filename="lecture.md",
            title="Fallback lecture",
            file_type="markdown",
            page_count=1,
            chunk_count=1,
            char_count=68,
        )
        db.add(document)
        db.flush()
        db.add(
            Chunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="A neural network learns patterns from examples by adjusting its weights.",
                char_count=68,
                embedding="[0.0,1.0]",
            )
        )
        db.commit()
        document_id = document.id

    llm = LLMService(Settings(llm_api_key="test-key", embedding_dimensions=128))
    with patch.object(llm, "_complete", new=AsyncMock(side_effect=RuntimeError("offline"))) as complete:
        app.dependency_overrides[get_llm_service] = lambda: llm
        response = client.post(
            "/api/chat",
            json={"document_id": document_id, "message": "What does a neural network learn?"},
        )

    assert response.status_code == 200
    assert response.json()["fallback_used"] is True
    assert "[Page 1]" in response.json()["answer"]
    complete.assert_awaited_once()


def test_upload_rejects_files_over_the_limit(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("large.md", b"x" * (1024 * 1024 + 1), "text/markdown")},
    )

    assert response.status_code == 413
    assert "1 MB" in response.json()["detail"]
