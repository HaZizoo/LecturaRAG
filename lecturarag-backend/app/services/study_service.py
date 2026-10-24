"""Flashcard and quiz orchestration: generation, persistence and grading."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Flashcard, FlashcardDeck, Quiz, QuizAttempt, QuizQuestion
from app.schemas import QuizQuestionResult
from app.services.document_service import load_document_index
from app.services.llm_service import ChatChunk, LLMService
from app.services.rag_engine import select_study_chunks

STUDY_CHUNK_LIMIT = 14


def _study_material(db: Session, document: Document) -> list[ChatChunk]:
    index = load_document_index(db, document.id)
    return list(select_study_chunks(index, limit=STUDY_CHUNK_LIMIT))


def _parse_options(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(option) for option in parsed]


async def generate_deck(
    db: Session,
    document: Document,
    llm: LLMService,
    count: int = 12,
) -> FlashcardDeck:
    material = _study_material(db, document)
    if not material:
        raise ValueError("This document has no indexed text to study.")

    result = await llm.generate_flashcards(material, count)
    if not result.cards:
        raise ValueError(
            "Not enough structured text in this document to build flashcards. "
            "Try a lecture with longer prose."
        )

    deck = FlashcardDeck(
        document_id=document.id,
        title=f"{document.title} - Flashcards",
        model=result.model,
        fallback_used=result.fallback_used,
    )
    db.add(deck)
    db.flush()

    for position, card in enumerate(result.cards):
        db.add(
            Flashcard(
                deck_id=deck.id,
                order_index=position,
                front=card.front,
                back=card.back,
                source_page=card.source_page,
                difficulty=card.difficulty,
                status="new",
            )
        )

    db.commit()
    db.refresh(deck)
    return deck


async def generate_quiz(
    db: Session,
    document: Document,
    llm: LLMService,
    num_questions: int = 6,
) -> Quiz:
    material = _study_material(db, document)
    if not material:
        raise ValueError("This document has no indexed text to quiz on.")

    result = await llm.generate_quiz(material, num_questions)
    if not result.questions:
        raise ValueError(
            "Not enough distinct facts in this document to build a quiz. "
            "Try a longer lecture."
        )

    quiz = Quiz(
        document_id=document.id,
        title=f"{document.title} - Quiz",
        model=result.model,
        fallback_used=result.fallback_used,
    )
    db.add(quiz)
    db.flush()

    for position, question in enumerate(result.questions):
        db.add(
            QuizQuestion(
                quiz_id=quiz.id,
                order_index=position,
                question=question.question,
                options=json.dumps(question.options, ensure_ascii=False),
                correct_index=question.correct_index,
                explanation=question.explanation,
                source_page=question.source_page,
            )
        )

    db.commit()
    db.refresh(quiz)
    return quiz


def latest_decks(db: Session, document_id: str, limit: int = 10) -> list[FlashcardDeck]:
    statement = (
        select(FlashcardDeck)
        .where(FlashcardDeck.document_id == document_id)
        .order_by(FlashcardDeck.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def latest_quizzes(db: Session, document_id: str, limit: int = 10) -> list[Quiz]:
    statement = (
        select(Quiz)
        .where(Quiz.document_id == document_id)
        .order_by(Quiz.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())


def check_answer(
    db: Session,
    quiz_id: str,
    question_id: str,
    selected_index: int | None,
) -> tuple[QuizQuestion, bool]:
    """Validate one answer for instant feedback without persisting an attempt."""

    question = db.get(QuizQuestion, question_id)
    if question is None or question.quiz_id != quiz_id:
        raise ValueError("Question not found for this quiz.")

    options = _parse_options(question.options)
    if selected_index is not None and not 0 <= selected_index < len(options):
        raise ValueError("selected_index is outside the available options.")

    return question, selected_index is not None and selected_index == question.correct_index


def grade_attempt(
    db: Session,
    quiz: Quiz,
    answers: Sequence[int | None],
) -> tuple[QuizAttempt, list[QuizQuestionResult]]:
    questions = sorted(quiz.questions, key=lambda question: question.order_index)
    if len(answers) != len(questions):
        raise ValueError(
            f"This quiz has {len(questions)} questions but {len(answers)} answers were submitted."
        )

    score = 0
    results: list[QuizQuestionResult] = []
    stored_answers: list[int | None] = []

    for question, selected in zip(questions, answers):
        options = _parse_options(question.options)
        if selected is not None and not 0 <= selected < len(options):
            selected = None
        is_correct = selected is not None and selected == question.correct_index
        if is_correct:
            score += 1
        stored_answers.append(selected)
        results.append(
            QuizQuestionResult(
                question_id=question.id,
                order_index=question.order_index,
                question=question.question,
                options=options,
                selected_index=selected,
                correct_index=question.correct_index,
                is_correct=is_correct,
                explanation=question.explanation,
                source_page=question.source_page,
            )
        )

    total = len(questions)
    percentage = round((score / total) * 100, 1) if total else 0.0
    attempt = QuizAttempt(
        quiz_id=quiz.id,
        score=score,
        total=total,
        percentage=percentage,
        answers=json.dumps(stored_answers),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt, results
