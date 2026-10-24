"""Deterministic extractive fallback engine.

When ``LLM_API_KEY`` is absent (or the provider errors), LecturaRAG must still
be fully demoable. This module builds real answers, flashcards and quizzes by
extracting and scoring sentences from the actual uploaded chunks, so every
generated item keeps a genuine page citation.

Everything here is deterministic: no randomness beyond a hash-seeded shuffle,
which means the same document always produces the same study material.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.schemas import FlashcardDraft, QuizQuestionDraft
from app.services.rag_engine import (
    STOPWORDS,
    IndexedChunk,
    RetrievedChunk,
    content_terms,
    split_sentences,
    strip_markdown,
    term_set,
)

_DEFINITION_RE = re.compile(
    r"^(?:The\s+)?(?P<term>[A-Z][A-Za-z0-9 &/+().'-]{2,60}?)\s+"
    r"(?:is|are|was|were|refers to|refer to|means|describes|describe|"
    r"can be defined as|is defined as|are defined as)\s+"
    r"(?P<body>\S.{20,})$"
)

_VAGUE_TERMS = {
    "this",
    "that",
    "these",
    "those",
    "there",
    "here",
    "it",
    "they",
    "we",
    "you",
    "the",
    "a",
    "an",
    "in",
    "on",
    "for",
    "as",
    "by",
}

_KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#-]{4,}")

_NON_DEFINITION_PREFIXES = {
    "popular",
    "important",
    "useful",
    "common",
    "often",
    "widely",
    "easy",
    "hard",
    "difficult",
    "efficient",
    "slow",
    "fast",
    "simple",
    "helpful",
    "typically",
    "generally",
    "usually",
    "only",
    "also",
}

_TERM_BLOCKLIST = {
    "it",
    "this",
    "these",
    "those",
    "there",
    "here",
    "they",
    "we",
    "you",
    "he",
    "she",
    "how",
    "what",
    "why",
    "when",
    "where",
    "which",
    "who",
    "covers",
    "cover",
    "include",
    "includes",
    "contain",
    "contains",
    "show",
    "shows",
    "use",
    "uses",
    "explain",
    "explains",
    "mean",
    "means",
}

_ANSWER_STOPWORDS = {
    "summarize",
    "summarise",
    "summary",
    "overview",
    "explain",
    "describe",
    "document",
    "lecture",
    "page",
    "pages",
    "according",
    "tell",
    "about",
    "what",
    "which",
    "does",
    "say",
    "says",
    "give",
    "me",
    "please",
    "key",
    "takeaway",
    "takeaways",
    "point",
    "points",
    "concept",
    "concepts",
    "main",
    "core",
    "idea",
    "ideas",
    "important",
    "revise",
    "revision",
    "exam",
    "exams",
    "study",
    "learn",
    "need",
    "should",
}


@dataclass(frozen=True)
class Fact:
    sentence: str
    page_number: int
    chunk_index: int
    order: int
    term: str | None
    definition_body: str | None
    keywords: tuple[str, ...]
    score: float


@dataclass(frozen=True)
class FallbackAnswer:
    answer: str
    used_pages: tuple[int, ...]
    grounded: bool


def _seed(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit - 3)
    if cut < limit // 2:
        cut = limit - 3
    return text[:cut].rstrip(" ,;:-") + "..."


def _clean_term(term: str) -> str:
    term = re.sub(r"\s+", " ", term).strip(" .,:;-'\"()")
    term = re.sub(r"^(the|a|an)\s+", "", term, flags=re.IGNORECASE)
    return term[:80].strip()


def _pick_keyword(sentence: str, exclude: set[str]) -> str | None:
    candidates = [
        match.group(0)
        for match in _KEYWORD_RE.finditer(sentence)
        if match.group(0).lower() not in STOPWORDS
        and match.group(0).lower() not in _VAGUE_TERMS
        and match.group(0).lower() not in exclude
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda word: (-len(word), sentence.find(word)))
    return candidates[0]


def _match_case(reference: str, candidate: str) -> str:
    if not candidate:
        return candidate
    if reference[:1].isupper():
        return candidate[:1].upper() + candidate[1:]
    return candidate[:1].lower() + candidate[1:]


def _lemma(word: str) -> str:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    return re.sub(r"(ies|es|s)$", "", cleaned)


def _blank_out(sentence: str, keyword: str) -> str:
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    if not pattern.search(sentence):
        return sentence
    return pattern.sub("_____", sentence, count=1)


def _is_definition(sentence: str) -> re.Match[str] | None:
    match = _DEFINITION_RE.match(sentence)
    if not match:
        return None

    term = _clean_term(match.group("term"))
    words = [word.lower() for word in re.findall(r"[A-Za-z0-9+#]+", term)]
    if not words or len(words) > 6:
        return None
    if words[0] in _VAGUE_TERMS or words[0] in _TERM_BLOCKLIST:
        return None
    if any(word in _TERM_BLOCKLIST for word in words):
        return None

    body = match.group("body").strip()
    first_word = re.match(r"[A-Za-z']+", body)
    if first_word and first_word.group(0).lower() in _NON_DEFINITION_PREFIXES:
        return None
    if body.lower().startswith("a good fit"):
        return None
    return match


def _difficulty(sentence: str) -> str:
    key_terms = {
        word for word in re.findall(r"[A-Za-z]{5,}", sentence) if word.lower() not in STOPWORDS
    }
    if len(sentence) > 220 or len(key_terms) >= 9 or re.search(r"\d", sentence):
        return "hard"
    if len(sentence) < 140 and len(key_terms) <= 3:
        return "easy"
    return "medium"


def collect_facts(chunks: Iterable[IndexedChunk | RetrievedChunk]) -> list[Fact]:
    """Turn chunks into ranked, de-duplicated factual sentences."""

    facts: list[Fact] = []
    seen: set[str] = set()
    order = 0

    for chunk in chunks:
        for sentence in split_sentences(chunk.content):
            normalized = strip_markdown(sentence).lower()
            if normalized in seen:
                continue
            seen.add(normalized)

            definition = _is_definition(sentence)
            term = _clean_term(definition.group("term")) if definition else None
            body = definition.group("body").strip() if definition else None

            keywords: list[str] = []
            for word in _KEYWORD_RE.findall(sentence):
                lowered = word.lower()
                if lowered in _VAGUE_TERMS or lowered in STOPWORDS or lowered in keywords:
                    continue
                keywords.append(lowered)
            keywords = keywords[:8]

            score = 1.0
            if definition:
                score += 3.0
            if re.search(r"\d", sentence):
                score += 0.6
            if 80 <= len(sentence) <= 260:
                score += 0.4
            score += min(len(keywords), 6) * 0.12

            facts.append(
                Fact(
                    sentence=strip_markdown(sentence),
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    order=order,
                    term=term,
                    definition_body=body,
                    keywords=tuple(keywords),
                    score=score,
                )
            )
            order += 1

    facts.sort(key=lambda fact: (-fact.score, fact.page_number, fact.chunk_index, fact.order))
    return facts


def _round_robin_by_page(facts: Sequence[Fact]) -> list[Fact]:
    buckets: dict[int, deque[Fact]] = {}
    for fact in facts:
        buckets.setdefault(fact.page_number, deque()).append(fact)

    ordered: list[Fact] = []
    pages = sorted(buckets)
    while pages:
        for page in list(pages):
            queue = buckets[page]
            if queue:
                ordered.append(queue.popleft())
            if not queue:
                pages.remove(page)
    return ordered


def _term_pool(facts: Sequence[Fact]) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for fact in facts:
        for word in _KEYWORD_RE.findall(fact.sentence):
            lowered = word.lower()
            if lowered in _VAGUE_TERMS or lowered in STOPWORDS:
                continue
            counts[lowered] += 1
            display.setdefault(lowered, word)
    ordered = sorted(counts, key=lambda term: (-counts[term], -len(term), term))
    return [display[term] for term in ordered]


# --------------------------------------------------------------------------- #
# Flashcards
# --------------------------------------------------------------------------- #
def build_flashcards(chunks: Sequence[IndexedChunk | RetrievedChunk], count: int) -> list[FlashcardDraft]:
    facts = collect_facts(chunks)
    if not facts:
        return []

    cards: list[FlashcardDraft] = []
    fronts: set[str] = set()

    def add(front: str, back: str, page: int, difficulty: str) -> None:
        key = front.lower().strip()
        if key in fronts or len(cards) >= count:
            return
        if not front.strip() or not back.strip():
            return
        fronts.add(key)
        cards.append(
            FlashcardDraft(
                front=_clip(front, 380),
                back=_clip(back, 1100),
                source_page=max(1, page),
                difficulty=difficulty,  # type: ignore[arg-type]
            )
        )

    ranked = _round_robin_by_page(facts)
    for fact in ranked:
        if len(cards) >= count:
            break
        difficulty = _difficulty(fact.sentence)
        if fact.term and fact.definition_body:
            add(
                f'Define "{fact.term}" in the context of this lecture.',
                fact.sentence,
                fact.page_number,
                difficulty,
            )
            continue

        keyword = _pick_keyword(fact.sentence, set())
        if keyword:
            add(
                f"Fill in the blank: {_blank_out(fact.sentence, keyword)}",
                f"{keyword}: {fact.sentence}",
                fact.page_number,
                difficulty,
            )

    # Top up with reverse cards if the lecture is short but has a few facts.
    if len(cards) < count:
        for fact in ranked:
            if len(cards) >= count:
                break
            keyword = _pick_keyword(fact.sentence, set())
            if not keyword:
                continue
            add(
                f"Explain the role of {keyword} in the context of page {fact.page_number}.",
                fact.sentence,
                fact.page_number,
                _difficulty(fact.sentence),
            )

    return cards[:count]


# --------------------------------------------------------------------------- #
# Quizzes
# --------------------------------------------------------------------------- #
def _build_definition_question(fact: Fact, facts: Sequence[Fact]) -> QuizQuestionDraft | None:
    if not fact.term:
        return None

    correct = _clip(fact.sentence, 180)
    distractors: list[str] = []
    seen = {correct.lower()}

    for other in facts:
        if len(distractors) >= 3:
            break
        if other.sentence.lower() == fact.sentence.lower():
            continue
        if other.term and other.term.lower() == fact.term.lower():
            continue
        candidate = _clip(other.sentence, 180)
        if candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        distractors.append(candidate)

    if len(distractors) < 3:
        return None

    options = [correct, *distractors]
    random.Random(_seed(f"definition:{fact.sentence}")).shuffle(options)
    return QuizQuestionDraft(
        question=f'Which statement about "{fact.term}" is correct according to the lecture?',
        options=options,
        correct_index=options.index(correct),
        explanation=f"According to page {fact.page_number}: {_clip(fact.sentence, 500)}",
        source_page=max(1, fact.page_number),
    )


def _build_cloze_question(
    fact: Fact, term_pool: Sequence[str], used_questions: set[str]
) -> QuizQuestionDraft | None:
    keyword = _pick_keyword(fact.sentence, set())
    if not keyword:
        return None

    blanked = _blank_out(fact.sentence, keyword)
    if "_____" not in blanked:
        return None
    if len(blanked) > 500:
        blanked = _clip(blanked, 500)

    question = f'Complete this statement from page {fact.page_number}: "{blanked}"'
    if question.lower() in used_questions:
        return None

    distractors: list[str] = []
    seen = {keyword.lower()}
    for candidate in term_pool:
        if len(distractors) >= 3:
            break
        lowered = candidate.lower()
        if lowered in seen or _lemma(candidate) == _lemma(keyword):
            continue
        if re.search(rf"\b{re.escape(candidate)}\b", fact.sentence, re.IGNORECASE):
            continue
        seen.add(lowered)
        distractors.append(_match_case(keyword, candidate))

    if len(distractors) < 3:
        for other in fact.keywords:
            if len(distractors) >= 3:
                break
            if other in seen or _lemma(other) == _lemma(keyword):
                continue
            seen.add(other)
            distractors.append(_match_case(keyword, other))

    if len(distractors) < 3:
        return None

    options = [keyword, *distractors]
    random.Random(_seed(f"cloze:{blanked}")).shuffle(options)
    return QuizQuestionDraft(
        question=question,
        options=options,
        correct_index=options.index(keyword),
        explanation=f"Page {fact.page_number}: {_clip(fact.sentence, 500)}",
        source_page=max(1, fact.page_number),
    )


def _build_statement_question(
    fact: Fact, facts: Sequence[Fact], used_questions: set[str]
) -> QuizQuestionDraft | None:
    question = f"Which statement about the material on page {fact.page_number} is accurate?"
    if question.lower() in used_questions:
        return None

    correct = _clip(fact.sentence, 170)
    distractors: list[str] = []
    seen = {correct.lower()}

    for other in facts:
        if len(distractors) >= 3:
            break
        if other.page_number == fact.page_number and other.order == fact.order:
            continue
        candidate = _clip(other.sentence, 170)
        if candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        distractors.append(candidate)

    if len(distractors) < 3:
        return None

    options = [correct, *distractors]
    random.Random(_seed(f"statement:{fact.sentence}")).shuffle(options)
    return QuizQuestionDraft(
        question=question,
        options=options,
        correct_index=options.index(correct),
        explanation=f"Page {fact.page_number}: {_clip(fact.sentence, 500)}",
        source_page=max(1, fact.page_number),
    )


def build_quiz(chunks: Sequence[IndexedChunk | RetrievedChunk], count: int) -> list[QuizQuestionDraft]:
    facts = collect_facts(chunks)
    if len(facts) < 4:
        return []

    term_pool = _term_pool(facts)
    definitions = [fact for fact in facts if fact.term and fact.definition_body]
    non_definitions = [fact for fact in facts if not (fact.term and fact.definition_body)]

    questions: list[QuizQuestionDraft] = []
    used: set[str] = set()

    def accept(candidate: QuizQuestionDraft | None) -> None:
        if candidate is None or len(questions) >= count:
            return
        key = candidate.question.lower()
        if key in used:
            return
        used.add(key)
        questions.append(candidate)

    definition_target = max(1, count // 2)
    for fact in _round_robin_by_page(definitions):
        if len(questions) >= definition_target:
            break
        accept(_build_definition_question(fact, facts))

    for fact in _round_robin_by_page(non_definitions):
        if len(questions) >= count:
            break
        accept(_build_cloze_question(fact, term_pool, used))

    if len(questions) < count:
        for fact in _round_robin_by_page(facts):
            if len(questions) >= count:
                break
            accept(_build_statement_question(fact, facts, used))

    return questions[:count]


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def answer_question(question: str, retrieved: Sequence[RetrievedChunk]) -> FallbackAnswer:
    """Answer extractively from the actual retrieved chunks, with citations."""

    if not retrieved:
        return FallbackAnswer(
            answer="I couldn't retrieve any content for this document yet.",
            used_pages=(),
            grounded=False,
        )

    question_words = term_set(question)
    question_terms = question_words - _ANSWER_STOPWORDS
    explicit_summary = bool(
        {"summarize", "summarise", "summary", "overview", "takeaway"} & question_words
    )
    broad_request = not question_terms
    if explicit_summary or broad_request:
        lines: list[str] = []
        pages: list[int] = []
        seen_pages: set[int] = set()
        for chunk in retrieved:
            if len(lines) >= 3:
                break
            if chunk.page_number in seen_pages:
                continue
            sentences = split_sentences(chunk.content, min_length=40)
            if not sentences:
                continue
            seen_pages.add(chunk.page_number)
            lines.append(f"- {_clip(sentences[0], 320)} [Page {chunk.page_number}]")
            pages.append(chunk.page_number)
        if lines:
            return FallbackAnswer(
                answer="Key points from the uploaded lecture:\n\n" + "\n".join(lines),
                used_pages=tuple(pages),
                grounded=True,
            )

    scored: list[tuple[float, int, int, int, str]] = []
    for chunk_rank, chunk in enumerate(retrieved):
        for sentence_rank, sentence in enumerate(split_sentences(chunk.content, min_length=25)):
            if not question_terms:
                continue
            overlap = len(question_terms & term_set(sentence))
            if overlap < 2 and not (overlap == 1 and chunk_rank == 0):
                continue
            score = overlap * 1.4 + chunk.similarity * 0.8
            if sentence_rank == 0:
                score += 0.15
            scored.append((score, chunk.page_number, chunk.chunk_index, sentence_rank, sentence))

    scored.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    chosen: list[tuple[int, int, int, str]] = []
    seen_sentences: set[str] = set()
    per_chunk: Counter[int] = Counter()

    for _score, page, chunk_index, sentence_rank, sentence in scored:
        if len(chosen) >= 3:
            break
        key = sentence.lower()
        if key in seen_sentences or per_chunk[chunk_index] >= 2:
            continue
        seen_sentences.add(key)
        per_chunk[chunk_index] += 1
        chosen.append((page, chunk_index, sentence_rank, sentence))

    if chosen:
        # Add one supporting sentence from the best chunk when the answer is thin.
        top_chunk = retrieved[0]
        from_top = sum(1 for item in chosen if item[1] == top_chunk.chunk_index)
        if from_top < 2 and len(chosen) < 4:
            chosen_texts = {item[3] for item in chosen}
            for sentence in split_sentences(top_chunk.content, min_length=25):
                if sentence in chosen_texts:
                    continue
                chosen.append((top_chunk.page_number, top_chunk.chunk_index, 999, sentence))
                break

        chosen.sort(key=lambda item: (item[0], item[1], item[2]))
        bullets = "\n".join(f"- {_clip(sentence, 380)} [Page {page}]" for page, _c, _r, sentence in chosen)
        return FallbackAnswer(
            answer=f"Based on the uploaded lecture:\n\n{bullets}",
            used_pages=tuple(dict.fromkeys(page for page, *_rest in chosen)),
            grounded=True,
        )

    if retrieved[0].similarity >= 0.05:
        snippet = split_sentences(retrieved[0].content, min_length=25)
        passage = snippet[0] if snippet else _clip(retrieved[0].content, 320)
        return FallbackAnswer(
            answer=(
                "I couldn't find a direct answer in the lecture. "
                f"The closest passage is on page {retrieved[0].page_number}:\n\n"
                f"{_clip(passage, 360)} [Page {retrieved[0].page_number}]"
            ),
            used_pages=(retrieved[0].page_number,),
            grounded=False,
        )

    return FallbackAnswer(
        answer=(
            "I couldn't find content in this document that answers that question. "
            "Try asking about a topic covered in the uploaded pages."
        ),
        used_pages=(),
        grounded=False,
    )
