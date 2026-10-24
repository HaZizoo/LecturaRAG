"""LecturaRAG FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.database import engine, init_db
from app.routers import chat, documents, flashcards, quizzes
from app.schemas import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("lecturarag")

settings: Settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info(
        "LecturaRAG started (llm=%s)",
        settings.llm_model if settings.llm_configured else "deterministic-fallback",
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Upload a PDF or Markdown lecture, chat with it using retrieval-augmented "
        "generation, and generate cited flashcards and quizzes. Works without an "
        "LLM key through a deterministic extractive engine."
    ),
    lifespan=lifespan,
)

# Vite falls back to the next free port when 5173 is taken. Allow any loopback
# port so local testing never fails CORS, while production origins still come
# from the explicit CORS_ORIGINS list.
_LOOPBACK_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=_LOOPBACK_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(flashcards.router)
app.include_router(quizzes.router)


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        llm_mode="openai-compatible" if settings.llm_configured else "deterministic-fallback",
        database=engine.url.get_backend_name(),
    )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
