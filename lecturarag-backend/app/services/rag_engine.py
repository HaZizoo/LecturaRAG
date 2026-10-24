"""Local retrieval-augmented-generation engine.

The engine deliberately avoids external vector-database services so the
project is fully runnable offline:

* PDFs are parsed with ``pypdf`` page by page; Markdown is split into
  heading-delimited sections, so every unit keeps exact page provenance.
* Text is chunked with a sliding window (500 chars / 100 overlap by default),
  never crossing a page boundary, so a chunk's page number is always exact.
* Embeddings are deterministic signed-hash bag-of-words vectors persisted as
  JSON next to the chunk rows in SQLite. Cosine similarity is computed in
  pure Python; no model download or API key is needed.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.config import Settings, get_settings

# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    page_number: int
    content: str
    embedding: list[float]


@dataclass(frozen=True)
class PreparedDocument:
    filename: str
    title: str
    file_type: str
    pages: list[ParsedPage]
    chunks: list[TextChunk]

    @property
    def char_count(self) -> int:
        return sum(len(page.text) for page in self.pages)


@dataclass(frozen=True)
class IndexedChunk:
    chunk_index: int
    page_number: int
    content: str
    embedding: list[float]
    chunk_id: str | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_index: int
    page_number: int
    content: str
    similarity: float
    chunk_id: str | None = None


# --------------------------------------------------------------------------- #
# Text utilities
# --------------------------------------------------------------------------- #

PAGE_MARKER = re.compile(r"<!--\s*page\s*:\s*(\d+)\s*-->", re.IGNORECASE)
_H2_RE = re.compile(r"(?m)^##[ \t]+(.+?)[ \t]*$")
_H1_RE = re.compile(r"(?m)^#[ \t]+(.+?)[ \t]*$")
_H1_TITLE_RE = re.compile(r"(?m)^#[ \t]+(.+?)[ \t]*$")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+\S")
_WORD_RE = re.compile(r"[a-z][a-z0-9+#]*")

STOPWORDS: frozenset[str] = frozenset(
    """
    a about above after again against all also am among an and any are as at be
    because been before being below between both but by can cannot could did do
    does doing done down during each either else etc few for from further get
    given had has have having here how however if in into is it its itself just
    least less like made make many may might more most much must my near neither
    no nor not now of off often on once one only or other our out over own per
    put rather same see seem shall she should since so some such than that the
    their them then there these they this those though through thus to too under
    until up upon us use used using very via was we were what when where which
    while who whom why will with within without would yet you your
    """.split()
)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_markdown(text: str) -> str:
    """Flatten Markdown syntax so extracted sentences read naturally."""

    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)([*_])(?!\s)(.*?)(?<!\s)\1(?!\w)", r"\2", text)
    text = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+", "", text)
    text = re.sub(r"(?m)^[ \t]*>[ \t]?", "", text)
    text = re.sub(r"(?m)^[ \t]*[-*+][ \t]+", "", text)
    text = re.sub(r"(?m)^[ \t]*\d+[.)][ \t]+", "", text)
    return normalize_whitespace(text)


def split_sentences(text: str, *, min_length: int = 30, max_length: int = 420) -> list[str]:
    """Split a passage into stand-alone sentences.

    Bullet lists and headings become their own units; overly long sentences are
    cut on word boundaries so generated study material stays readable.
    """

    flattened = strip_markdown(_drop_headings(text))
    if not flattened:
        return []

    sentences: list[str] = []
    for paragraph in re.split(r"\n{2,}", flattened):
        for line in _merge_wrapped_lines(paragraph):
            if not line or line.startswith(("```", "|", "---")):
                continue
            for candidate in _SENTENCE_END_RE.split(line):
                candidate = candidate.strip()
                if len(candidate) < min_length or len(candidate.split()) < 4:
                    continue
                if not re.search(r"[A-Za-z]{3}", candidate):
                    continue
                first_letter = next((char for char in candidate if char.isalpha()), "")
                if not first_letter or not first_letter.isupper():
                    continue
                sentences.extend(_truncate(candidate, max_length))
    return sentences


def _drop_headings(text: str) -> str:
    """Keep headings in the retrieval index but out of extracted sentences."""

    return "\n".join(
        line for line in text.split("\n") if not _HEADING_LINE_RE.match(line.strip())
    )


def _merge_wrapped_lines(paragraph: str) -> list[str]:
    """Re-join hard-wrapped PDF/Markdown lines that continue a sentence.

    A new line that starts lowercase and follows a line without terminal
    punctuation is a wrap, not a new bullet or heading.
    """

    merged: list[str] = []
    for raw_line in paragraph.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if merged and not re.search(r"[.!?;:]$", merged[-1]) and line[:1].islower():
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _truncate(sentence: str, max_length: int) -> list[str]:
    if len(sentence) <= max_length:
        return [sentence]
    pieces: list[str] = []
    remaining = sentence
    while len(remaining) > max_length:
        cut = remaining.rfind(" ", 0, max_length)
        if cut < max_length // 2:
            cut = max_length
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def content_terms(text: str) -> list[str]:
    """Content-bearing stems, used for lexical scoring and fallback material."""

    terms = []
    for token in tokenize(text):
        if len(token) < 3 or token in STOPWORDS or token.isdigit():
            continue
        terms.append(_stem(token))
    return terms


def term_set(text: str) -> set[str]:
    return set(content_terms(text))


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def detect_file_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    raise ValueError("Unsupported file type. Upload a PDF (.pdf) or Markdown (.md) lecture.")


def extract_pages(filename: str, data: bytes) -> tuple[str, list[ParsedPage]]:
    """Return ``(file_type, pages)`` with exact page numbering per page."""

    file_type = detect_file_type(filename)
    if not data:
        raise ValueError("The uploaded file is empty.")
    if file_type == "pdf":
        return file_type, _parse_pdf(data)
    return file_type, _parse_markdown(data)


def _parse_pdf(data: bytes) -> list[ParsedPage]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pragma: no cover - depends on malformed input
        raise ValueError(f"Could not read the PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on the PDF
            raise ValueError("Password-protected PDFs are not supported.") from exc

    pages: list[ParsedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception:  # pragma: no cover - one broken page should not fail the upload
            raw = ""
        text = normalize_whitespace(raw)
        if len(text) >= 2:
            pages.append(ParsedPage(page_number=index, text=text))

    if not pages:
        raise ValueError(
            "No extractable text found in the PDF. Scanned documents need OCR before upload."
        )
    return pages


def _parse_markdown(data: bytes) -> list[ParsedPage]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("The uploaded Markdown file is empty.")

    marker_numbers = [int(number) for number in PAGE_MARKER.findall(text)]
    if marker_numbers:
        return _pages_from_markers(text)

    heading_matches = list(_H2_RE.finditer(text)) or list(_H1_RE.finditer(text))
    if heading_matches:
        return _pages_from_headings(text, heading_matches)

    horizontal_rules = re.split(r"(?m)^[ \t]*---[ \t]*$", text)
    sections = [normalize_whitespace(section) for section in horizontal_rules if section.strip()]
    if len(sections) > 1:
        return [ParsedPage(page_number=i, text=section) for i, section in enumerate(sections, start=1)]
    return [ParsedPage(page_number=1, text=normalize_whitespace(text))]


def _pages_from_markers(text: str) -> list[ParsedPage]:
    parts = PAGE_MARKER.split(text)
    pages: list[ParsedPage] = []
    preamble = normalize_whitespace(parts[0])
    if preamble:
        pages.append(ParsedPage(page_number=1, text=preamble))
    for i in range(1, len(parts), 2):
        number = int(parts[i])
        body = normalize_whitespace(parts[i + 1] if i + 1 < len(parts) else "")
        if body:
            pages.append(ParsedPage(page_number=number, text=body))
    if not pages:
        raise ValueError("The Markdown file contains only page markers.")
    return pages


def _pages_from_headings(text: str, matches: list[re.Match[str]]) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    preamble = normalize_whitespace(text[: matches[0].start()])
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = normalize_whitespace(text[match.start() : end])
        if not section:
            continue
        if not pages and preamble:
            section = f"{preamble}\n\n{section}"
        pages.append(ParsedPage(page_number=len(pages) + 1, text=section))
    return pages or [ParsedPage(page_number=1, text=normalize_whitespace(text))]


def extract_title(filename: str, pages: Sequence[ParsedPage], file_type: str, data: bytes) -> str:
    if file_type == "markdown":
        for page in pages:
            for line in page.text.split("\n"):
                line = line.strip()
                if line.startswith("#"):
                    title = line.lstrip("#").strip()
                    if title:
                        return title[:200]
    if file_type == "pdf":
        try:
            metadata = PdfReader(io.BytesIO(data)).metadata or {}
            title = (metadata.get("/Title") or "").strip()
            if title and title.lower() not in {"untitled", "document"}:
                return title[:200]
        except Exception:  # pragma: no cover - metadata is optional
            pass
    return humanize_stem(filename)


def humanize_stem(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_-]+", " ", stem).strip()
    return (stem or "Untitled lecture")[:200]


# --------------------------------------------------------------------------- #
# Chunking
# --------------------------------------------------------------------------- #


def chunk_page(text: str, page_number: int, start_index: int, *, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Sliding-window chunking that stops at sentence boundaries when possible."""

    text = text.strip()
    if not text:
        return []

    size = max(200, chunk_size)
    overlap = min(max(0, overlap), size - 50)
    chunks: list[TextChunk] = []
    position = 0
    total = len(text)
    index = start_index

    while position < total:
        end = min(position + size, total)
        if end < total:
            boundary = _last_sentence_boundary(text, position + int(size * 0.6), end)
            if boundary > position + int(size * 0.4):
                end = boundary
        piece = text[position:end].strip()
        if piece:
            chunks.append(
                TextChunk(chunk_index=index, page_number=page_number, content=piece, embedding=[])
            )
            index += 1
        if end >= total:
            break
        next_position = end - overlap
        if next_position <= position:
            next_position = end
        next_position = _snap_to_word_start(text, next_position)
        position = next_position

    return chunks


def _last_sentence_boundary(text: str, lower: int, upper: int) -> int:
    window = text[lower:upper]
    best = -1
    for match in re.finditer(r"[.!?;:](?=\s)|\n\n|\n(?=[-*+0-9])", window):
        best = match.end()
    return lower + best if best > 0 else -1


def _snap_to_word_start(text: str, position: int) -> int:
    if position <= 0 or position >= len(text):
        return position
    if text[position - 1].isspace() or text[position].isspace():
        return position
    limit = min(position + 40, len(text))
    probe = text.find(" ", position, limit)
    return probe + 1 if probe != -1 else position


def chunk_pages(pages: Sequence[ParsedPage], *, chunk_size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for page in pages:
        chunks.extend(
            chunk_page(
                page.text,
                page.page_number,
                start_index=len(chunks),
                chunk_size=chunk_size,
                overlap=overlap,
            )
        )
    return chunks


# --------------------------------------------------------------------------- #
# Embeddings & retrieval
# --------------------------------------------------------------------------- #


def embed_text(text: str, dimensions: int | None = None) -> list[float]:
    """Deterministic signed feature hashing, L2-normalised."""

    dims = dimensions or get_settings().embedding_dimensions
    vector = [0.0] * dims
    tokens = [_stem(token) for token in tokenize(text) if token not in STOPWORDS and len(token) > 1]
    if not tokens:
        return vector

    features: Counter[str] = Counter(tokens)
    for left, right in zip(tokens, tokens[1:]):
        features[f"{left} {right}"] += 1

    for feature, count in features.items():
        weight = 1.0 + math.log(count)
        if " " in feature:
            weight *= 0.6
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        hashed = int.from_bytes(digest, "big")
        bucket = hashed % dims
        sign = 1.0 if (hashed >> 17) & 1 == 0 else -1.0
        vector[bucket] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [round(value / norm, 6) for value in vector]


def serialize_embedding(vector: Sequence[float]) -> str:
    return json.dumps([round(float(value), 6) for value in vector], separators=(",", ":"))


def deserialize_embedding(raw: str | None) -> list[float]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [float(value) for value in parsed if isinstance(value, (int, float))]


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def prepare_document(
    filename: str,
    data: bytes,
    *,
    settings: Settings | None = None,
    title_override: str | None = None,
) -> PreparedDocument:
    config = settings or get_settings()
    safe_name = Path(filename).name or "lecture.pdf"
    file_type, pages = extract_pages(safe_name, data)
    chunks = chunk_pages(pages, chunk_size=config.chunk_size, overlap=config.chunk_overlap)
    if not chunks:
        raise ValueError("No readable text could be extracted from this document.")

    embedded = [
        TextChunk(
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            content=chunk.content,
            embedding=embed_text(chunk.content, config.embedding_dimensions),
        )
        for chunk in chunks
    ]
    title = (title_override or extract_title(safe_name, pages, file_type, data)).strip()
    return PreparedDocument(
        filename=safe_name,
        title=title[:200] or humanize_stem(safe_name),
        file_type=file_type,
        pages=pages,
        chunks=embedded,
    )


def load_index(chunks: Iterable[Any]) -> list[IndexedChunk]:
    """Convert ORM chunk rows into retrieval records."""

    index: list[IndexedChunk] = []
    for row in chunks:
        index.append(
            IndexedChunk(
                chunk_id=getattr(row, "id", None),
                chunk_index=int(getattr(row, "chunk_index", 0)),
                page_number=int(getattr(row, "page_number", 1)),
                content=str(getattr(row, "content", "")),
                embedding=deserialize_embedding(getattr(row, "embedding", None)),
            )
        )
    return index


def retrieve(
    index: Sequence[IndexedChunk],
    query: str,
    *,
    top_k: int = 4,
    dimensions: int | None = None,
) -> list[RetrievedChunk]:
    """Return the top-k chunks ranked by blended cosine + lexical overlap."""

    query = query.strip()
    if not index or not query:
        return []

    query_vector = embed_text(query, dimensions)
    query_terms = term_set(query)
    scored: list[RetrievedChunk] = []

    for chunk in index:
        if not chunk.content.strip():
            continue
        cosine = max(0.0, cosine_similarity(query_vector, chunk.embedding))
        if query_terms:
            overlap = len(query_terms & term_set(chunk.content)) / len(query_terms)
        else:
            overlap = 0.0
        score = min(1.0, cosine * 0.85 + overlap * 0.15)
        scored.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                content=chunk.content,
                similarity=round(score, 4),
            )
        )

    scored.sort(key=lambda item: (-item.similarity, item.chunk_index))
    top = scored[: max(1, top_k)]
    return top


def select_study_chunks(index: Sequence[IndexedChunk], *, limit: int = 14) -> list[IndexedChunk]:
    """Spread selection across pages so decks/quizzes cover the whole lecture."""

    if not index:
        return []

    by_page: dict[int, list[IndexedChunk]] = {}
    for chunk in index:
        by_page.setdefault(chunk.page_number, []).append(chunk)

    selected: list[IndexedChunk] = []
    seen: set[int] = set()
    for page in sorted(by_page):
        richest = max(by_page[page], key=lambda item: (len(item.content), -item.chunk_index))
        if len(selected) >= limit:
            break
        selected.append(richest)
        seen.add(richest.chunk_index)

    if len(selected) < limit:
        remaining = [chunk for chunk in index if chunk.chunk_index not in seen]
        step = max(1, math.ceil(len(remaining) / max(1, limit - len(selected))))
        for chunk in remaining[::step]:
            if len(selected) >= limit:
                break
            selected.append(chunk)
            seen.add(chunk.chunk_index)

    selected.sort(key=lambda item: item.chunk_index)
    return selected[:limit]


def build_context_block(chunks: Sequence[RetrievedChunk], *, max_chars: int = 9000) -> str:
    """Render retrieved chunks for the LLM prompt, with provenance headers."""

    blocks: list[str] = []
    used = 0
    for chunk in chunks:
        header = f"[Page {chunk.page_number} | chunk {chunk.chunk_index} | similarity {chunk.similarity:.2f}]"
        body = chunk.content.strip()
        block = f"{header}\n{body}"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n---\n\n".join(blocks)
