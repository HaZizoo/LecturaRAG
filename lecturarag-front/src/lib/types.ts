export type Difficulty = "easy" | "medium" | "hard";
export type CardStatus = "new" | "needs_review" | "mastered";
export type TabId = "chat" | "flashcards" | "quiz";

export interface DocumentSummary {
  id: string;
  filename: string;
  title: string;
  file_type: "pdf" | "markdown";
  page_count: number;
  chunk_count: number;
  char_count: number;
  created_at: string;
}

export interface Citation {
  page_number: number;
  chunk_index: number;
  similarity: number;
  snippet: string;
}

export interface SourceChunk {
  page_number: number;
  chunk_index: number;
  similarity: number;
  content: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  model: string;
  fallback_used: boolean;
  created_at: string;
}

export interface ChatEntry extends ChatMessage {
  sources?: SourceChunk[];
}

export interface ChatResponse {
  message_id: string;
  document_id: string;
  answer: string;
  citations: Citation[];
  sources: SourceChunk[];
  model: string;
  fallback_used: boolean;
  created_at: string;
}

export interface Flashcard {
  id: string;
  order_index: number;
  front: string;
  back: string;
  source_page: number;
  difficulty: Difficulty;
  status: CardStatus;
}

export interface Deck {
  id: string;
  document_id: string;
  title: string;
  model: string;
  fallback_used: boolean;
  created_at: string;
  cards: Flashcard[];
}

export interface QuizQuestion {
  id: string;
  order_index: number;
  question: string;
  options: string[];
  source_page: number;
}

export interface Quiz {
  id: string;
  document_id: string;
  title: string;
  model: string;
  fallback_used: boolean;
  created_at: string;
  questions: QuizQuestion[];
}

export interface QuizQuestionResult {
  question_id: string;
  order_index: number;
  question: string;
  options: string[];
  selected_index: number | null;
  correct_index: number;
  is_correct: boolean;
  explanation: string;
  source_page: number;
}

export interface QuizAttempt {
  attempt_id: string;
  quiz_id: string;
  score: number;
  total: number;
  percentage: number;
  results: QuizQuestionResult[];
  created_at: string;
}

export interface AnswerCheck {
  question_id: string;
  selected_index: number | null;
  correct_index: number;
  is_correct: boolean;
  explanation: string;
  source_page: number;
}

export interface Health {
  status: "ok";
  app: string;
  version: string;
  llm_mode: "openai-compatible" | "deterministic-fallback";
  database: string;
}
