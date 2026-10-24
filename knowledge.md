# Project: LecturaRAG — AI Study & RAG Workspace
## Architecture: Full-Stack Monorepo (`lecturarag-backend` + `lecturarag-front`)

### Tech Stack
- **Backend (`lecturarag-backend`):** Python 3.11+, FastAPI, Uvicorn, Pydantic (strict JSON validation), PyMuPDF (`fitz`) or `pypdf` for PDF parsing, ChromaDB (local persistent vector store) or in-memory TF-IDF/Vector embeddings, OpenAI/Groq/Anthropic compatible LLM SDK, SQLite + SQLAlchemy for persisting documents, flashcards, and quizzes.
- **Frontend (`lecturarag-front`):** React 19, TypeScript, Vite, Tailwind CSS, Lucide React icons.

### Core Modules & User Stories
1. **Document Ingestion & Vectorization (RAG Core):**
   - Users upload PDF or Markdown lecture files.
   - Backend extracts text page-by-page, splits text into overlapping chunks (500 chars, 100 overlap) preserving `page_number` metadata, and indexes them for semantic retrieval.
2. **RAG Chat Interface (Chat App Tier-3):**
   - Users chat with their uploaded document in real time.
   - Backend retrieves the top-k most relevant chunks and prompts the LLM to answer strictly using the context, returning exact `[Page X]` citations and source snippets.
3. **AI Flashcard Deck Generator (Flashcards App Tier-2):**
   - One-click generation of 10-15 interactive Q&A flashcards from the document using strict Pydantic structured output (`front`, `back`, `source_page`, `difficulty`).
   - Frontend renders a 3D flip-card UI with spaced-repetition tracking ("Mastered" vs "Needs Review").
4. **AI Interactive Quiz Engine (Quiz App Tier-1/3):**
   - Generates a multiple-choice quiz (4 options per question, `correct_index`, and `explanation` citing the page number).
   - Frontend tracks score, timer, and displays detailed post-quiz explanations.

### Engineering Standards
- Zero hardcoded API keys; strictly use `.env` with a clean fallback/mock mode if no LLM key is set so recruiters can test the full UI immediately after cloning.
- Strict CORS allowing `http://localhost:5173`.
- No AI watermarks or "Co-Authored-By" tags in code or git history.