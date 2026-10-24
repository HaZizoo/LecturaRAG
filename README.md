# LecturaRAG

A full-stack, citation-first study workspace for lecture PDFs and Markdown notes. Upload a lecture, then chat with it, drill 3D flashcards, and take a timed quiz — every answer points back to the exact page it came from.

The portfolio detail: **it works with no API key.** When `LLM_API_KEY` is empty (or the provider fails), a deterministic extractive engine builds cited answers, flashcards, and quiz questions directly from the uploaded text, so the whole app can be cloned and tested offline.

## Features

| Area | What it does |
| --- | --- |
| **Library & upload** | Drag-and-drop or browse PDF/Markdown files (up to 20 MB). Shows page count and indexed chunks per lecture, with selection and deletion. |
| **RAG chat** | Asks questions against the active lecture, retrieves the top 4 chunks, and renders answers with clickable `[Page X]` badges that expand to the exact source excerpt, similarity score, and chunk index. |
| **3D flashcards** | CSS 3D flip on click, `Space`, or `Enter`; arrow-key card navigation; difficulty filters (Easy / Medium / Hard); mastery progress bar; **Mastered** and **Review again** persist to the backend. |
| **Timed quiz** | 30 seconds per question, live score, instant per-answer validation, a page-cited explanation after each answer, and a graded results screen with a full answer review. |
| **Offline fallback** | Deterministic extractive answers and generated study material when no LLM is configured — no network required. |

## Tech stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Lucide icons
- **Backend:** Python 3.11+, FastAPI, Pydantic v2 (strict schemas), SQLAlchemy, SQLite
- **Parsing:** `pypdf` for PDFs, custom Markdown page extraction
- **Retrieval:** local deterministic signed-hash TF vectors + lexical overlap, stored as JSON in SQLite — no external vector database
- **LLM:** any OpenAI-compatible `/chat/completions` endpoint (OpenAI, Groq, Together, vLLM, Ollama, …)

## Project structure

```text
LecturaRAG/
├── package.json                  # monorepo scripts (dev, build, seed, typecheck)
├── README.md
├── lecturarag-backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, lifespan, CORS, /health
│   │   ├── config.py             # env-driven settings
│   │   ├── database.py           # SQLite engine + session factory
│   │   ├── models.py             # Document, Chunk, ChatMessage, Deck, Flashcard, Quiz…
│   │   ├── schemas.py            # strict Pydantic v2 request/response models
│   │   ├── routers/              # documents, chat, flashcards, quizzes
│   │   └── services/
│   │       ├── rag_engine.py     # parsing, page-aware chunking, embeddings, top-k
│   │       ├── llm_service.py    # OpenAI-compatible client + JSON validation
│   │       ├── fallback_engine.py# deterministic cited answers and study material
│   │       └── document_service.py / study_service.py
│   ├── samples/                  # sample CS lecture (10 pages)
│   ├── seed_sample.py            # seeds lecture, chunks, 12 cards, 8 quiz questions
│   ├── requirements.txt
│   └── .env.example
└── lecturarag-front/
    ├── src/
    │   ├── App.tsx               # workspace shell and view state
    │   ├── components/           # sidebar, chat, flashcards, quiz, UI primitives
    │   ├── hooks/                # documents, chat, flashcards, quiz, health
    │   └── lib/                  # typed API client and shared types
    └── vite.config.ts            # dev proxy for /api and /health
```

## Quick start

**Prerequisites:** Python 3.11+ and Node.js 20+ (npm).

### 1. Backend

```bash
cd lecturarag-backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cd ..
```

### 2. Frontend dependencies

```bash
npm run setup
```

### 3. Seed the sample lecture

```bash
npm run seed
```

This creates the SQLite database and preloads **“Introduction to Algorithms & Neural Networks”** (10 pages, 20 chunks, 12 flashcards, 8 quiz questions). Re-run with `python lecturarag-backend/seed_sample.py --reset` to rebuild it.

### 4. Run both servers

```bash
npm run dev
```

- Frontend: <http://localhost:5173> (Vite picks the next free port if 5173 is busy)
- API: <http://localhost:8000>
- Interactive API docs: <http://localhost:8000/docs>

No `.env` is required. To use a real model, copy `lecturarag-backend/.env.example` to `lecturarag-backend/.env` and set:

```dotenv
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

Leave `LLM_API_KEY` empty to use the deterministic engine. The backend reports the active mode at `GET /health` (`llm_mode: "deterministic-fallback" | "llm"`).

## Root scripts

| Script | Description |
| --- | --- |
| `npm run dev` | Runs FastAPI (`:8000`) and Vite together with `concurrently` |
| `npm run build` | Type-checks and builds the frontend |
| `npm run seed` | Seeds the sample lecture (run inside an activated venv) |
| `npm run typecheck` | `tsc --noEmit` for the frontend |
| `npm run test:api` | Runs the in-process FastAPI test suite (no server needed) |
| `npm run setup` | Installs root and frontend npm dependencies |

## API

All endpoints are served under `/api`; the frontend proxies them to `http://127.0.0.1:8000` in development.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/documents/upload` | Upload and index a PDF/Markdown lecture |
| `GET` | `/api/documents` | List indexed documents |
| `GET` | `/api/documents/{document_id}` | Document metadata |
| `DELETE` | `/api/documents/{document_id}` | Delete a document and its study data |
| `POST` | `/api/chat` | Ask a cited question about a document |
| `GET` | `/api/chat/{document_id}/history` | Chat transcript |
| `POST` | `/api/flashcards/generate` | Generate a flashcard deck |
| `GET` | `/api/flashcards/{document_id}` | List decks and cards |
| `PATCH` | `/api/flashcards/cards/{card_id}` | Persist mastery status |
| `POST` | `/api/quizzes/generate` | Generate a multiple-choice quiz |
| `GET` | `/api/quizzes/{document_id}` | List quizzes |
| `POST` | `/api/quizzes/check` | Validate one answer instantly |
| `POST` | `/api/quizzes/attempt` | Submit and grade a full attempt |

## How retrieval works

1. PDFs are parsed page by page with `pypdf`; Markdown splits at H1/H2 sections (or explicit `<!-- page: N -->` markers). Page numbers are preserved exactly.
2. Text is chunked at **500 characters with 100 characters of overlap**, snapping to sentence boundaries and never crossing a page.
3. Each chunk gets a deterministic signed-hash term-frequency vector (512 dimensions) blended with lexical overlap, stored locally as JSON on the chunk row.
4. A query is embedded the same way; cosine similarity ranks chunks, and the **top 4** are returned with page, chunk index, similarity score, and full text.
5. With an LLM configured, those chunks are the only context in a JSON-mode prompt; malformed or failed responses fall back to the deterministic extractor. With no key, the extractor answers directly from the retrieved sentences.

## Verification

```bash
cd lecturarag-front
npx tsc --noEmit
npm run build
```

Both complete with zero TypeScript or bundler errors.

The backend suite uses `TestClient` in-process (no server, no network) and a throwaway SQLite database:

```bash
cd lecturarag-backend
python tests/test_api.py
# or, from the repo root with the venv active:
npm run test:api
```

It covers health, loopback CORS, upload validation (empty, oversized, corrupt/encrypted PDF, path traversal), short-document edge cases, cited chat, flashcard generation and mastery, quiz validation and grading, and cascading deletes across every child table.

The app was also exercised end to end in the browser: upload/index, cited chat with expandable sources, flashcard flip and mastery persistence, quiz validation, timing, grading, and results review.

## License

MIT — use it, fork it, and cite your sources.
