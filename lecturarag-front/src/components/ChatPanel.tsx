import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  ArrowUpRight,
  Loader2,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import type { ChatEntry, DocumentSummary } from "../lib/types";
import { ChatMessageBubble } from "./ChatMessageBubble";
import { ErrorNotice, SkeletonBlock } from "./ui";

const SUGGESTIONS = [
  "Give me the key takeaways.",
  "Summarize this lecture.",
  "What is the hardest concept on page 1?",
  "How should I revise this for an exam?",
];

interface ChatPanelProps {
  document: DocumentSummary;
  messages: ChatEntry[];
  isLoadingHistory: boolean;
  isSending: boolean;
  error: string | null;
  onSend: (message: string) => Promise<boolean>;
  onRetry: () => void;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-3" aria-live="polite" aria-label="Generating answer">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-line bg-panel-raised text-brass-300">
        <Sparkles size={14} aria-hidden="true" />
      </div>
      <div className="flex items-center gap-2 rounded-panel border border-line-soft bg-panel/60 px-4 py-3">
        <span className="flex items-end gap-1" aria-hidden="true">
          <span className="size-1.5 animate-blink rounded-full bg-brass-300" />
          <span className="size-1.5 animate-blink rounded-full bg-brass-300" />
          <span className="size-1.5 animate-blink rounded-full bg-brass-300" />
        </span>
        <span className="text-[11px] text-faint">Reading the lecture…</span>
      </div>
    </div>
  );
}

export function ChatPanel({
  document,
  messages,
  isLoadingHistory,
  isSending,
  error,
  onSend,
  onRetry,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages.length, isSending]);

  const sendMessage = async (text: string, clearDraft: boolean) => {
    const value = text.trim();
    if (!value || isSending) return;
    if (clearDraft) setDraft("");
    const sent = await onSend(value);
    if (!sent && clearDraft) {
      setDraft((current) => (current.trim() ? current : value));
    }
  };

  const empty = messages.length === 0 && !isLoadingHistory;

  return (
    <section className="flex h-full min-h-0 flex-col">
      <div ref={scrollRef} className="scrollbar-slim min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
          {isLoadingHistory ? (
            <div className="space-y-5" aria-busy="true" aria-label="Loading conversation">
              <SkeletonBlock className="ml-auto h-14 w-2/3" />
              <div className="flex gap-3">
                <div className="skeleton size-8 shrink-0 rounded-lg" />
                <SkeletonBlock className="h-32 flex-1" />
              </div>
            </div>
          ) : empty ? (
            <div className="py-6 sm:py-12">
              <div className="flex size-11 items-center justify-center rounded-panel border border-brass-400/25 bg-brass-400/[0.07] text-brass-300">
                <MessageSquareText size={20} strokeWidth={1.7} aria-hidden="true" />
              </div>
              <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
                Document indexed
              </p>
              <h2 className="mt-2 max-w-xl font-display text-3xl leading-tight text-ink sm:text-4xl">
                Interrogate the lecture, <span className="italic text-brass-300">not the internet.</span>
              </h2>
              <p className="mt-3 max-w-lg text-sm leading-relaxed text-muted">
                Ask anything about <span className="text-ink">{document.title}</span>. Answers
                stay grounded in your pages, and every citation opens the exact excerpt.
              </p>

              <div className="mt-7 grid gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void sendMessage(suggestion, false)}
                    disabled={isSending}
                    className="group flex items-center justify-between gap-3 rounded-panel border border-line-soft bg-white/[0.015] px-3.5 py-3 text-left text-xs text-muted transition-colors hover:border-brass-400/30 hover:bg-brass-400/[0.04] hover:text-ink disabled:opacity-50"
                  >
                    {suggestion}
                    <ArrowUpRight
                      size={13}
                      className="shrink-0 text-faint transition-colors group-hover:text-brass-300"
                      aria-hidden="true"
                    />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message) => (
                <ChatMessageBubble key={message.id} message={message} />
              ))}
              {isSending ? <TypingIndicator /> : null}
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 border-t border-line-soft bg-canvas/70 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto w-full max-w-3xl">
          {error ? (
            <div className="mb-2">
              <ErrorNotice message={error} onRetry={onRetry} compact />
            </div>
          ) : null}

          <form
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft, true);
            }}
            className="relative rounded-xl border border-line bg-panel-raised transition-colors focus-within:border-brass-400/45"
          >
            <label htmlFor="chat-input" className="sr-only">
              Ask a question about {document.title}
            </label>
            <textarea
              id="chat-input"
              rows={1}
              value={draft}
              maxLength={4000}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage(draft, true);
                }
              }}
              placeholder="Ask about a concept, a formula, or a page…"
              className="max-h-40 min-h-12 w-full resize-none bg-transparent px-4 py-3.5 pr-14 text-sm text-ink placeholder:text-faint focus:outline-none"
            />
            <button
              type="submit"
              disabled={!draft.trim() || isSending}
              aria-label={isSending ? "Sending question" : "Send question"}
              className="absolute bottom-2 right-2 inline-flex size-8 items-center justify-center rounded-lg bg-brass-400 text-[#211509] transition-colors hover:bg-brass-300 disabled:bg-line disabled:text-faint"
            >
              {isSending ? (
                <Loader2 size={15} className="animate-spin" aria-hidden="true" />
              ) : (
                <ArrowUp size={15} strokeWidth={2.4} aria-hidden="true" />
              )}
            </button>
          </form>

          <div className="mt-2 flex items-center justify-between gap-3 text-[10px] text-faint">
            <span>Grounded in your lecture · tap a citation to verify it</span>
            <span className="hidden whitespace-nowrap sm:inline">
              Enter to send · Shift+Enter for a new line
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
