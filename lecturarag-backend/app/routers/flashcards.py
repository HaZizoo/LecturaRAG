"""Flashcard deck endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Flashcard, FlashcardDeck
from app.schemas import (
    DeckRead,
    FlashcardDeckListResponse,
    FlashcardGenerateRequest,
    FlashcardRead,
    FlashcardStatusUpdate,
)
from app.services.document_service import get_document
from app.services.llm_service import LLMService, get_llm_service
from app.services.study_service import generate_deck, latest_decks

router = APIRouter(prefix="/api/flashcards", tags=["flashcards"])


def _serialize_card(card: Flashcard) -> FlashcardRead:
    return FlashcardRead(
        id=card.id,
        order_index=card.order_index,
        front=card.front,
        back=card.back,
        source_page=card.source_page,
        difficulty=card.difficulty,  # type: ignore[arg-type]
        status=card.status,  # type: ignore[arg-type]
    )


def _serialize_deck(deck: FlashcardDeck) -> DeckRead:
    cards = sorted(deck.cards, key=lambda card: card.order_index)
    return DeckRead(
        id=deck.id,
        document_id=deck.document_id,
        title=deck.title,
        model=deck.model,
        fallback_used=deck.fallback_used,
        created_at=deck.created_at,
        cards=[_serialize_card(card) for card in cards],
    )


@router.post(
    "/generate",
    response_model=DeckRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a flashcard deck from a document",
)
async def generate_flashcards(
    payload: FlashcardGenerateRequest,
    db: Session = Depends(get_db),
    llm: LLMService = Depends(get_llm_service),
) -> DeckRead:
    document = get_document(db, payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        deck = await generate_deck(db, document, llm, count=payload.count)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_deck(deck)


@router.get(
    "/{document_id}",
    response_model=FlashcardDeckListResponse,
    summary="List flashcard decks for a document",
)
def list_flashcards(document_id: str, db: Session = Depends(get_db)) -> FlashcardDeckListResponse:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    decks = latest_decks(db, document_id)
    return FlashcardDeckListResponse(
        document_id=document_id,
        decks=[_serialize_deck(deck) for deck in decks],
    )


@router.patch(
    "/cards/{card_id}",
    response_model=FlashcardRead,
    summary="Update spaced-repetition status for a card",
)
def update_card_status(
    card_id: str,
    payload: FlashcardStatusUpdate,
    db: Session = Depends(get_db),
) -> FlashcardRead:
    card = db.get(Flashcard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Flashcard not found.")

    card.status = payload.status
    db.commit()
    db.refresh(card)
    return _serialize_card(card)
