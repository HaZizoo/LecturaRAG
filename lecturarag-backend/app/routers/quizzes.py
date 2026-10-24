"""Quiz endpoints: generation, listing and server-side grading."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Quiz, QuizQuestion
from app.schemas import (
    QuizAnswerCheckRequest,
    QuizAnswerCheckResponse,
    QuizAttemptRequest,
    QuizAttemptResponse,
    QuizGenerateRequest,
    QuizListResponse,
    QuizQuestionRead,
    QuizRead,
)
from app.services.document_service import get_document
from app.services.llm_service import LLMService, get_llm_service
from app.services.study_service import (
    check_answer,
    generate_quiz,
    grade_attempt,
    latest_quizzes,
)

router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


def _options(question: QuizQuestion) -> list[str]:
    try:
        parsed = json.loads(question.options)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(option) for option in parsed]


def _serialize_quiz(quiz: Quiz) -> QuizRead:
    questions = sorted(quiz.questions, key=lambda question: question.order_index)
    return QuizRead(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        model=quiz.model,
        fallback_used=quiz.fallback_used,
        created_at=quiz.created_at,
        questions=[
            QuizQuestionRead(
                id=question.id,
                order_index=question.order_index,
                question=question.question,
                options=_options(question),
                source_page=question.source_page,
            )
            for question in questions
        ],
    )


@router.post(
    "/generate",
    response_model=QuizRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a multiple-choice quiz from a document",
)
async def generate_quiz_endpoint(
    payload: QuizGenerateRequest,
    db: Session = Depends(get_db),
    llm: LLMService = Depends(get_llm_service),
) -> QuizRead:
    document = get_document(db, payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        quiz = await generate_quiz(db, document, llm, num_questions=payload.num_questions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_quiz(quiz)


@router.post(
    "/check",
    response_model=QuizAnswerCheckResponse,
    summary="Validate a single answer for instant feedback",
)
def check_single_answer(
    payload: QuizAnswerCheckRequest,
    db: Session = Depends(get_db),
) -> QuizAnswerCheckResponse:
    quiz = db.get(Quiz, payload.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    try:
        question, is_correct = check_answer(
            db, quiz.id, payload.question_id, payload.selected_index
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QuizAnswerCheckResponse(
        question_id=question.id,
        selected_index=payload.selected_index,
        correct_index=question.correct_index,
        is_correct=is_correct,
        explanation=question.explanation,
        source_page=question.source_page,
    )


@router.post(
    "/attempt",
    response_model=QuizAttemptResponse,
    summary="Submit answers and receive a graded breakdown",
)
def submit_attempt(
    payload: QuizAttemptRequest,
    db: Session = Depends(get_db),
) -> QuizAttemptResponse:
    quiz = db.get(Quiz, payload.quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    try:
        attempt, results = grade_attempt(db, quiz, payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return QuizAttemptResponse(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        score=attempt.score,
        total=attempt.total,
        percentage=attempt.percentage,
        results=results,
        created_at=attempt.created_at,
    )


@router.get(
    "/{document_id}",
    response_model=QuizListResponse,
    summary="List quizzes for a document",
)
def list_quizzes(document_id: str, db: Session = Depends(get_db)) -> QuizListResponse:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    quizzes = latest_quizzes(db, document_id)
    return QuizListResponse(
        document_id=document_id,
        quizzes=[_serialize_quiz(quiz) for quiz in quizzes],
    )
