#!/usr/bin/env python
"""Seed LecturaRAG with a complete sample lecture, flashcard deck and quiz.

The script always uses the deterministic extractive engine, so the seeded
content is reproducible and no API key (or network) is required:

    python seed_sample.py            # create the sample if missing
    python seed_sample.py --reset    # replace any previously seeded sample
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Document  # noqa: E402
from app.services.document_service import ingest_document  # noqa: E402
from app.services.llm_service import LLMService  # noqa: E402
from app.services.study_service import generate_deck, generate_quiz  # noqa: E402

SAMPLE_FILENAME = "introduction_to_algorithms_and_neural_networks.md"
SAMPLE_PATH = BASE_DIR / "samples" / SAMPLE_FILENAME
SAMPLE_TITLE = "Introduction to Algorithms & Neural Networks"
FLASHCARD_COUNT = 12
QUIZ_QUESTIONS = 8


async def seed(reset: bool) -> int:
    if not SAMPLE_PATH.is_file():
        print(f"Sample lecture not found: {SAMPLE_PATH}")
        return 1

    settings = get_settings()
    init_db()

    with SessionLocal() as db:
        existing = list(db.scalars(select(Document).where(Document.title == SAMPLE_TITLE)).all())
        if existing and not reset:
            print(f"Sample document already seeded: {existing[0].id}")
            print("Run with --reset to rebuild it.")
            return 0

        if existing:
            for document in existing:
                db.delete(document)
            db.commit()

        document = ingest_document(
            db,
            SAMPLE_FILENAME,
            SAMPLE_PATH.read_bytes(),
            settings=settings,
            title_override=SAMPLE_TITLE,
        )

        # Force the deterministic engine so seeded content never depends on a key.
        seed_llm = LLMService(settings.model_copy(update={"llm_api_key": ""}))
        deck = await generate_deck(db, document, seed_llm, count=FLASHCARD_COUNT)
        quiz = await generate_quiz(db, document, seed_llm, num_questions=QUIZ_QUESTIONS)

        print("")
        print("Seeded sample lecture")
        print("---------------------")
        print(f"Title:       {document.title}")
        print(f"Document ID: {document.id}")
        print(f"Pages:       {document.page_count}")
        print(f"Chunks:      {document.chunk_count} ({document.char_count} chars)")
        print(f"Flashcards:  {len(deck.cards)} cards")
        print(f"Quiz:        {len(quiz.questions)} questions")
        print(f"Database:    {settings.database_url}")
        print("")
        print("Try it:")
        print(f"  curl http://localhost:8000/api/documents/{document.id}")
        print("  curl -X POST http://localhost:8000/api/chat \\")
        print('       -H "Content-Type: application/json" \\')
        print(
            f'       -d \'{{"document_id": "{document.id}", '
            '"message": "How does backpropagation work?"}\''
        )
        print("")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed LecturaRAG with a sample lecture.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and rebuild the previously seeded sample document.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(seed(args.reset))
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"Seeding failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
