"""In-process API verification for LecturaRAG.

Run from the backend directory with an activated virtualenv:

    python tests/test_api.py

The suite uses FastAPI's TestClient, so it starts no server and exits on its
own. It writes to a throwaway SQLite database and removes it afterwards.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

# Configure the app before importing it: settings and the engine are created at
# import time. A one-MB upload limit keeps the oversized-file test cheap.
_TEMP_DIR = tempfile.TemporaryDirectory(prefix="lecturarag-test-")
_DB_PATH = Path(_TEMP_DIR.name) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH.as_posix()}"
os.environ["MAX_UPLOAD_MB"] = "1"
os.environ["LLM_API_KEY"] = ""
os.environ["CHUNK_SIZE"] = "500"
os.environ["CHUNK_OVERLAP"] = "100"

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfWriter  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    ChatMessage,
    Chunk,
    Document,
    Flashcard,
    FlashcardDeck,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.services.rag_engine import ParsedPage, chunk_pages  # noqa: E402

SAMPLE_PATH = BACKEND_ROOT / "samples" / "introduction_to_algorithms_and_neural_networks.md"
PASSED = 0


def check(condition: object, message: str) -> None:
    global PASSED
    if not condition:
        raise AssertionError(message)
    PASSED += 1


def _upload(
    client: TestClient,
    filename: str,
    payload: bytes,
    content_type: str = "text/markdown",
) -> httpx.Response:
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, payload, content_type)},
    )


def _count(model, *conditions) -> int:
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)


def run_suite(client: TestClient) -> None:
    # Health and CORS -----------------------------------------------------
    health = client.get("/health")
    check(health.status_code == 200, f"/health returned {health.status_code}")
    body = health.json()
    check(body["status"] == "ok", "health status is not ok")
    check(body["llm_mode"] == "deterministic-fallback", "expected deterministic fallback mode")

    for origin in (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ):
        preflight = client.options(
            "/api/chat",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        check(preflight.status_code == 200, f"CORS preflight failed for {origin}")
        check(
            preflight.headers.get("access-control-allow-origin") == origin,
            f"CORS did not echo {origin}",
        )

    # Upload validation ---------------------------------------------------
    check(_upload(client, "empty.md", b"").status_code == 400, "empty upload was not rejected")
    check(
        _upload(client, "notes.txt", b"# not allowed").status_code == 400,
        "unsupported extension was not rejected",
    )
    oversized = b"a" * (1024 * 1024 + 1)
    check(
        _upload(client, "huge.md", oversized).status_code == 413,
        "oversized upload was not rejected",
    )
    zero_page = _upload(
        client,
        "zero-page.md",
        b"<!-- page: 0 -->\n\nAn algorithm is a finite sequence of instructions.",
    )
    check(zero_page.status_code == 400, "page marker 0 was not rejected")

    corrupted = _upload(client, "broken.pdf", b"%PDF-1.7 this is not a PDF", "application/pdf")
    check(corrupted.status_code == 400, f"corrupted PDF returned {corrupted.status_code}")
    check("corrupt" in corrupted.json()["detail"].lower(), "corrupted PDF detail is unclear")

    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=200, height=200)
    encrypted_writer.encrypt("secret")
    encrypted_buffer = io.BytesIO()
    encrypted_writer.write(encrypted_buffer)
    encrypted = _upload(
        client,
        "locked.pdf",
        encrypted_buffer.getvalue(),
        "application/pdf",
    )
    check(encrypted.status_code == 400, "encrypted PDF was not rejected")
    check("password" in encrypted.json()["detail"].lower(), "encrypted PDF detail is unclear")

    blank_writer = PdfWriter()
    blank_writer.add_blank_page(width=200, height=200)
    blank_writer.add_blank_page(width=200, height=200)
    blank_buffer = io.BytesIO()
    blank_writer.write(blank_buffer)
    blank_pdf = _upload(client, "blank.pdf", blank_buffer.getvalue(), "application/pdf")
    check(blank_pdf.status_code == 400, "blank PDF was not rejected")
    check("text" in blank_pdf.json()["detail"].lower(), "blank PDF detail is unclear")

    # A blank page before real text must be skipped without shifting provenance.
    page_chunks = chunk_pages(
        [ParsedPage(page_number=1, text=""), ParsedPage(page_number=2, text="Real text " * 80)],
        chunk_size=500,
        overlap=100,
    )
    check(bool(page_chunks), "empty-page chunking produced nothing")
    check(all(chunk.page_number == 2 for chunk in page_chunks), "page number shifted past a blank page")

    # Short Markdown must not 500 ----------------------------------------
    short = _upload(client, "tiny.md", b"# Tiny\n\nNeural networks learn from data.")
    check(short.status_code == 201, f"short Markdown upload returned {short.status_code}")
    short_id = short.json()["document"]["id"]
    short_chat = client.post(
        "/api/chat",
        json={"document_id": short_id, "message": "Explain this."},
    )
    check(short_chat.status_code == 200, f"short-document chat returned {short_chat.status_code}")
    short_cards = client.post(
        "/api/flashcards/generate",
        json={"document_id": short_id, "count": 5},
    )
    check(short_cards.status_code in {201, 400}, "short-document flashcards crashed")
    short_quiz = client.post(
        "/api/quizzes/generate",
        json={"document_id": short_id, "num_questions": 3},
    )
    check(short_quiz.status_code in {201, 400}, "short-document quiz crashed")

    # Main seeded-style upload -------------------------------------------
    sample_bytes = SAMPLE_PATH.read_bytes()
    uploaded = _upload(client, "../../evil/introduction.md", sample_bytes)
    check(uploaded.status_code == 201, f"sample upload returned {uploaded.status_code}")
    document = uploaded.json()["document"]
    document_id = document["id"]
    check(document["filename"] == "introduction.md", "filename was not sanitized")
    check(document["file_type"] == "markdown", "file type was not detected")
    check(document["page_count"] >= 4, "sample did not index multiple pages")
    check(document["chunk_count"] >= 4, "sample did not index chunks")

    listed = client.get("/api/documents")
    check(listed.status_code == 200, "document list failed")
    check(
        any(item["id"] == document_id for item in listed.json()["documents"]),
        "uploaded document missing from list",
    )
    fetched = client.get(f"/api/documents/{document_id}")
    check(fetched.status_code == 200, "document lookup failed")
    check(fetched.json()["title"], "document title is empty")

    # RAG chat ------------------------------------------------------------
    chat = client.post(
        "/api/chat",
        json={"document_id": document_id, "message": "What is an algorithm?", "top_k": 4},
    )
    check(chat.status_code == 200, f"chat returned {chat.status_code}")
    answer = chat.json()
    check("[Page " in answer["answer"], "answer has no [Page X] citation")
    check(answer["citations"], "answer has no citation metadata")
    check(0 < len(answer["sources"]) <= 4, "retrieval did not return 1-4 sources")
    pages = {item["page_number"] for item in answer["citations"]}
    check(all(1 <= page <= document["page_count"] for page in pages), "citation page out of range")
    check(
        all(source["content"] for source in answer["sources"]),
        "citation source snippet is empty",
    )

    zero_overlap = client.post(
        "/api/chat",
        json={"document_id": document_id, "message": "zzzz qqqq xxxx"},
    )
    check(zero_overlap.status_code == 200, "zero-overlap query crashed")
    check("citations" in zero_overlap.json(), "zero-overlap response is malformed")

    history = client.get(f"/api/chat/{document_id}/history")
    check(history.status_code == 200, "chat history failed")
    roles = [message["role"] for message in history.json()["messages"]]
    check(roles.count("user") >= 2, "chat history lost user messages")
    check(roles.count("assistant") >= 2, "chat history lost assistant messages")

    # Flashcards ----------------------------------------------------------
    deck_response = client.post(
        "/api/flashcards/generate",
        json={"document_id": document_id, "count": 8},
    )
    check(deck_response.status_code == 201, f"flashcard generation returned {deck_response.status_code}")
    deck = deck_response.json()
    check(bool(deck["cards"]), "generated deck has no cards")
    card = deck["cards"][0]
    check(card["status"] == "new", "new card does not start as new")
    check(1 <= card["source_page"] <= document["page_count"], "card page out of range")

    updated = client.patch(
        f"/api/flashcards/cards/{card['id']}",
        json={"status": "mastered"},
    )
    check(updated.status_code == 200, "card status update failed")
    check(updated.json()["status"] == "mastered", "card mastery was not persisted")

    decks = client.get(f"/api/flashcards/{document_id}")
    check(decks.status_code == 200, "deck lookup failed")
    stored = decks.json()["decks"][0]["cards"]
    check(
        next(item for item in stored if item["id"] == card["id"])["status"] == "mastered",
        "card status missing after reload",
    )

    # Quizzes -------------------------------------------------------------
    quiz_response = client.post(
        "/api/quizzes/generate",
        json={"document_id": document_id, "num_questions": 4},
    )
    check(quiz_response.status_code == 201, f"quiz generation returned {quiz_response.status_code}")
    quiz = quiz_response.json()
    check(len(quiz["questions"]) >= 3, "quiz has too few questions")

    correct_answers: list[int] = []
    for question in quiz["questions"]:
        check(len(question["options"]) == 4, "question does not have four options")
        check(len(set(question["options"])) == 4, "question options are not distinct")
        checked = client.post(
            "/api/quizzes/check",
            json={
                "quiz_id": quiz["id"],
                "question_id": question["id"],
                "selected_index": None,
            },
        )
        check(checked.status_code == 200, "answer check failed")
        correct_index = checked.json()["correct_index"]
        check(0 <= correct_index < 4, "correct index out of range")
        correct_answers.append(correct_index)

        wrong_index = (correct_index + 1) % 4
        wrong = client.post(
            "/api/quizzes/check",
            json={
                "quiz_id": quiz["id"],
                "question_id": question["id"],
                "selected_index": wrong_index,
            },
        )
        check(wrong.status_code == 200, "wrong-answer check failed")
        check(wrong.json()["is_correct"] is False, "wrong answer accepted as correct")

        right = client.post(
            "/api/quizzes/check",
            json={
                "quiz_id": quiz["id"],
                "question_id": question["id"],
                "selected_index": correct_index,
            },
        )
        check(right.status_code == 200, "correct-answer check failed")
        check(right.json()["is_correct"] is True, "correct answer rejected")

    bad_length = client.post(
        "/api/quizzes/attempt",
        json={"quiz_id": quiz["id"], "answers": [0]},
    )
    check(bad_length.status_code == 400, "mismatched answer count was not rejected")

    attempt = client.post(
        "/api/quizzes/attempt",
        json={"quiz_id": quiz["id"], "answers": correct_answers},
    )
    check(attempt.status_code == 200, "quiz submission failed")
    graded = attempt.json()
    check(graded["score"] == graded["total"], "perfect attempt was not graded correctly")
    check(graded["percentage"] == 100.0, "perfect attempt percentage is wrong")

    quizzes = client.get(f"/api/quizzes/{document_id}")
    check(quizzes.status_code == 200, "quiz list failed")
    check(quizzes.json()["quizzes"], "generated quiz missing from list")

    # Cascading delete ----------------------------------------------------
    deleted = client.delete(f"/api/documents/{document_id}")
    check(deleted.status_code == 204, f"delete returned {deleted.status_code}")
    check(client.get(f"/api/documents/{document_id}").status_code == 404, "document still readable")

    with SessionLocal() as db:
        deck_ids = list(db.scalars(select(FlashcardDeck.id).where(FlashcardDeck.document_id == document_id)))
        quiz_ids = list(db.scalars(select(Quiz.id).where(Quiz.document_id == document_id)))

    check(_count(Document, Document.id == document_id) == 0, "document row still exists")
    check(_count(Chunk, Chunk.document_id == document_id) == 0, "orphaned chunks remain")
    check(
        _count(ChatMessage, ChatMessage.document_id == document_id) == 0,
        "orphaned chat messages remain",
    )
    check(
        _count(FlashcardDeck, FlashcardDeck.document_id == document_id) == 0,
        "orphaned decks remain",
    )
    check(
        _count(Flashcard, Flashcard.deck_id.in_(deck_ids)) == 0 if deck_ids else True,
        "orphaned flashcards remain",
    )
    check(_count(Quiz, Quiz.id.in_(quiz_ids)) == 0 if quiz_ids else True, "orphaned quizzes remain")
    check(_count(QuizQuestion, QuizQuestion.quiz_id.in_(quiz_ids)) == 0 if quiz_ids else True,
          "orphaned quiz questions remain")
    check(_count(QuizAttempt, QuizAttempt.quiz_id.in_(quiz_ids)) == 0 if quiz_ids else True,
          "orphaned quiz attempts remain")

    check(client.get("/api/chat/not-a-document/history").status_code == 404, "missing document history did not 404")
    check(
        client.post("/api/chat", json={"document_id": "missing", "message": "Hi"}).status_code == 404,
        "missing document chat did not 404",
    )


def main() -> int:
    print(f"LecturaRAG API suite | db={_DB_PATH}")
    try:
        with TestClient(app) as client:
            run_suite(client)
    except AssertionError as exc:
        print(f"\nFAILED after {PASSED} checks: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level CLI boundary
        print(f"\nERROR after {PASSED} checks: {type(exc).__name__}: {exc}")
        return 1
    finally:
        engine.dispose()
        _TEMP_DIR.cleanup()
    print(f"\nPASSED {PASSED} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
