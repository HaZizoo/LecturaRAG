import type {
  AnswerCheck,
  ChatMessage,
  ChatResponse,
  Deck,
  DocumentSummary,
  Health,
  Flashcard,
  Quiz,
  QuizAttempt,
} from "./types";

// Empty by default: Vite proxies /api and /health to the FastAPI server in dev
// and preview. Set VITE_API_BASE_URL when the API lives on another origin.
const CONFIGURED_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
const BASE_URL = CONFIGURED_BASE.replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Can't reach the LecturaRAG API. Start the backend on port 8000 and try again.",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the status-based fallback message.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}

export const api = {
  listDocuments: () =>
    request<{ documents: DocumentSummary[]; total: number }>("/api/documents"),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ document: DocumentSummary; message: string }>("/api/documents/upload", {
      method: "POST",
      body: form,
    });
  },

  deleteDocument: (documentId: string) =>
    request<void>(`/api/documents/${documentId}`, { method: "DELETE" }),

  getChatHistory: (documentId: string) =>
    request<{ document_id: string; messages: ChatMessage[] }>(
      `/api/chat/${documentId}/history`,
    ),

  sendChat: (documentId: string, message: string) =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId, message }),
    }),

  getDecks: (documentId: string) =>
    request<{ document_id: string; decks: Deck[] }>(`/api/flashcards/${documentId}`),

  generateDeck: (documentId: string, count = 12) =>
    request<Deck>("/api/flashcards/generate", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId, count }),
    }),

  updateCardStatus: (cardId: string, status: "new" | "needs_review" | "mastered") =>
    request<Flashcard>(`/api/flashcards/cards/${cardId}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  getQuizzes: (documentId: string) =>
    request<{ document_id: string; quizzes: Quiz[] }>(`/api/quizzes/${documentId}`),

  generateQuiz: (documentId: string, numQuestions = 6) =>
    request<Quiz>("/api/quizzes/generate", {
      method: "POST",
      body: JSON.stringify({ document_id: documentId, num_questions: numQuestions }),
    }),

  checkAnswer: (quizId: string, questionId: string, selectedIndex: number | null) =>
    request<AnswerCheck>("/api/quizzes/check", {
      method: "POST",
      body: JSON.stringify({
        quiz_id: quizId,
        question_id: questionId,
        selected_index: selectedIndex,
      }),
    }),

  submitQuizAttempt: (quizId: string, answers: (number | null)[]) =>
    request<QuizAttempt>("/api/quizzes/attempt", {
      method: "POST",
      body: JSON.stringify({ quiz_id: quizId, answers }),
    }),

  getHealth: () => request<Health>("/health"),
};
