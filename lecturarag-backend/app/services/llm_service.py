"""LLM access with a deterministic, fully-offline fallback.

`LLMService` talks to any OpenAI-compatible `/chat/completions` endpoint using
`LLM_API_KEY`, `LLM_BASE_URL` and `LLM_MODEL`. When the key is missing, or the
provider fails / returns unusable JSON, every method falls back to
`fallback_engine`, which extracts real sentences from the uploaded chunks. The
result is identical in shape, keeps genuine `[Page N]` citations, and needs no
network access at all.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.schemas import FlashcardDraft, QuizQuestionDraft
from app.services import fallback_engine
from app.services.rag_engine import IndexedChunk, RetrievedChunk

logger = logging.getLogger(__name__)

DETERMINISTIC_MODEL = "lecturarag-deterministic-v1"

ChatChunk = IndexedChunk | RetrievedChunk


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    model: str
    fallback_used: bool
    grounded: bool = True


@dataclass(frozen=True)
class GeneratedFlashcards:
    cards: list[FlashcardDraft]
    model: str
    fallback_used: bool


@dataclass(frozen=True)
class GeneratedQuiz:
    questions: list[QuizQuestionDraft]
    model: str
    fallback_used: bool


def _chunk_page(chunk: ChatChunk) -> int:
    return max(1, int(chunk.page_number))


def _format_material(chunks: Sequence[ChatChunk], *, max_chars: int = 9000) -> str:
    blocks: list[str] = []
    used = 0
    for chunk in chunks:
        block = f"[Page {_chunk_page(chunk)}]\n{chunk.content.strip()}"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n---\n\n".join(blocks)


def _allowed_pages(chunks: Sequence[ChatChunk]) -> set[int]:
    return {_chunk_page(chunk) for chunk in chunks} or {1}


def _nearest_page(page: int, allowed: set[int]) -> int:
    return min(allowed, key=lambda candidate: (abs(candidate - page), candidate))


def _clip(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object from the model.")
    return parsed


class LLMService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def available(self) -> bool:
        return self.settings.llm_configured

    @property
    def model_label(self) -> str:
        return self.settings.llm_model if self.available else DETERMINISTIC_MODEL

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    async def _complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.settings.llm_temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.settings.llm_max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.settings.llm_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.settings.llm_timeout_seconds, connect=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"LLM request failed: {type(exc).__name__}") from exc

            if json_mode and response.status_code in {400, 404, 422}:
                # Some gateways reject response_format; retry once as plain text.
                payload.pop("response_format", None)
                response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            detail = _clip(response.text, 240)
            raise RuntimeError(f"LLM provider returned HTTP {response.status_code}: {detail}")

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM provider returned an unexpected response shape.") from exc

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM provider returned an empty completion.")
        return content.strip()

    # ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #
    async def answer(self, question: str, chunks: Sequence[RetrievedChunk]) -> GeneratedAnswer:
        deterministic = fallback_engine.answer_question(question, chunks)
        fallback_result = GeneratedAnswer(
            text=deterministic.answer,
            model=DETERMINISTIC_MODEL,
            fallback_used=True,
            grounded=deterministic.grounded,
        )
        if not self.available or not chunks:
            return fallback_result

        system = (
            "You are LecturaRAG, a study assistant that answers ONLY from the supplied "
            "lecture excerpts.\n"
            "Rules:\n"
            "- Use only the excerpts. Never rely on outside knowledge or invent facts.\n"
            "- End every factual sentence with an exact citation marker such as [Page 3].\n"
            "- If the excerpts do not answer the question, say so plainly and mention a "
            "related topic that is covered.\n"
            "- Be concise: at most 160 words. Plain prose or a short bullet list."
        )
        user = f"Lecture excerpts:\n\n{_format_material(chunks)}\n\nQuestion: {question}"

        try:
            text = await self._complete(system=system, user=user, temperature=0.15)
        except Exception as exc:  # noqa: BLE001 - any provider failure must degrade gracefully
            logger.warning("LLM answer failed, using deterministic fallback: %s", exc)
            return fallback_result

        if not text.strip():
            return fallback_result
        return GeneratedAnswer(
            text=text.strip(),
            model=self.settings.llm_model,
            fallback_used=False,
        )

    # ------------------------------------------------------------------ #
    # Flashcards
    # ------------------------------------------------------------------ #
    async def generate_flashcards(self, chunks: Sequence[ChatChunk], count: int) -> GeneratedFlashcards:
        fallback_cards = fallback_engine.build_flashcards(chunks, count)
        fallback_result = GeneratedFlashcards(
            cards=fallback_cards,
            model=DETERMINISTIC_MODEL,
            fallback_used=True,
        )
        if not self.available or not chunks:
            return fallback_result

        allowed = _allowed_pages(chunks)
        system = (
            "You are an expert study coach. Turn lecture excerpts into flashcards.\n"
            'Respond with JSON only: {"cards": [{"front": "...", "back": "...", '
            '"source_page": 2, "difficulty": "easy"}]}\n'
            f"Create exactly {count} cards. Rules:\n"
            "- front is a question or a fill-in-the-blank prompt; back is a complete answer\n"
            "- every card must be answerable from the excerpts alone\n"
            f"- source_page must be one of {sorted(allowed)}\n"
            "- difficulty must be easy, medium or hard; no duplicate cards, no yes/no cards"
        )
        user = f"Lecture excerpts:\n\n{_format_material(chunks)}\n\nGenerate {count} flashcards."

        try:
            raw = await self._complete(system=system, user=user, json_mode=True, temperature=0.3)
            payload = _parse_json_object(raw)
            items = payload.get("cards", [])
            cards: list[FlashcardDraft] = []
            fronts: set[str] = set()

            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                try:
                    page = int(item.get("source_page", 1))
                except (TypeError, ValueError):
                    page = min(allowed)
                if page not in allowed:
                    page = _nearest_page(page, allowed)
                candidate = {
                    "front": _clip(item.get("front", ""), 380),
                    "back": _clip(item.get("back", ""), 1100),
                    "source_page": max(1, page),
                    "difficulty": str(item.get("difficulty", "medium")).lower(),
                }
                try:
                    draft = FlashcardDraft.model_validate(candidate, strict=False)
                except Exception:  # noqa: BLE001 - skip unusable cards
                    continue
                if draft.front.lower() in fronts:
                    continue
                fronts.add(draft.front.lower())
                cards.append(draft)

            if len(cards) < min(4, count):
                raise ValueError(f"Model produced only {len(cards)} usable flashcards.")
            return GeneratedFlashcards(
                cards=cards[:count],
                model=self.settings.llm_model,
                fallback_used=False,
            )
        except Exception as exc:  # noqa: BLE001 - any failure falls back
            logger.warning("LLM flashcard generation failed, using deterministic fallback: %s", exc)
            return fallback_result

    # ------------------------------------------------------------------ #
    # Quizzes
    # ------------------------------------------------------------------ #
    async def generate_quiz(self, chunks: Sequence[ChatChunk], count: int) -> GeneratedQuiz:
        fallback_questions = fallback_engine.build_quiz(chunks, count)
        fallback_result = GeneratedQuiz(
            questions=fallback_questions,
            model=DETERMINISTIC_MODEL,
            fallback_used=True,
        )
        if not self.available or not chunks:
            return fallback_result

        allowed = _allowed_pages(chunks)
        system = (
            "You are an exam author. Write multiple-choice questions from lecture excerpts.\n"
            'Respond with JSON only: {"questions": [{"question": "...", "options": '
            '["...", "...", "...", "..."], "correct_index": 0, "explanation": "...", '
            '"source_page": 2}]}\n'
            f"Create exactly {count} questions. Rules:\n"
            "- exactly 4 distinct options; exactly one is correct; correct_index is zero-based\n"
            "- distractors must be plausible but clearly wrong according to the excerpts\n"
            "- the explanation must state why the answer is correct and cite its page\n"
            f"- source_page must be one of {sorted(allowed)}"
        )
        user = f"Lecture excerpts:\n\n{_format_material(chunks)}\n\nWrite {count} questions."

        try:
            raw = await self._complete(system=system, user=user, json_mode=True, temperature=0.3)
            payload = _parse_json_object(raw)
            items = payload.get("questions", [])
            questions: list[QuizQuestionDraft] = []
            seen: set[str] = set()

            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict):
                    continue
                options = item.get("options")
                if not isinstance(options, list) or len(options) != 4:
                    continue
                cleaned: list[str] = []
                for option in options:
                    text = _clip(option, 220)
                    if not text or text.lower() in {value.lower() for value in cleaned}:
                        break
                    cleaned.append(text)
                if len(cleaned) != 4:
                    continue

                try:
                    correct_index = int(item.get("correct_index", -1))
                    page = int(item.get("source_page", 1))
                except (TypeError, ValueError):
                    continue
                if correct_index < 0 or correct_index > 3:
                    continue
                if page not in allowed:
                    page = _nearest_page(page, allowed)

                explanation = _clip(item.get("explanation", ""), 900)
                if not explanation:
                    continue
                if not re.search(r"\bpage\s*\d+", explanation, re.IGNORECASE):
                    explanation = f"Page {page}: {explanation}"

                try:
                    draft = QuizQuestionDraft.model_validate(
                        {
                            "question": _clip(item.get("question", ""), 500),
                            "options": cleaned,
                            "correct_index": correct_index,
                            "explanation": explanation,
                            "source_page": max(1, page),
                        },
                        strict=False,
                    )
                except Exception:  # noqa: BLE001 - skip unusable questions
                    continue
                if draft.question.lower() in seen:
                    continue
                seen.add(draft.question.lower())
                questions.append(draft)

            if len(questions) < min(3, count):
                raise ValueError(f"Model produced only {len(questions)} usable questions.")
            return GeneratedQuiz(
                questions=questions[:count],
                model=self.settings.llm_model,
                fallback_used=False,
            )
        except Exception as exc:  # noqa: BLE001 - any failure falls back
            logger.warning("LLM quiz generation failed, using deterministic fallback: %s", exc)
            return fallback_result


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService()
