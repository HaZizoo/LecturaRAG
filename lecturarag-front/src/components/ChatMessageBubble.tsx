import { useState, type ReactNode } from "react";
import { Quote, Sparkles } from "lucide-react";
import type { ChatEntry, Citation } from "../lib/types";
import { PageStamp } from "./ui";

const TOKEN_PATTERN = /(\[Page \d+\]|\*\*[^*]+\*\*)/g;

function renderInline(
  text: string,
  citations: Citation[],
  openPages: Set<number>,
  onTogglePage: (page: number) => void,
): ReactNode[] {
  const pieces = text.split(TOKEN_PATTERN);

  return pieces.map((piece, index) => {
    const pageMatch = /^\[Page (\d+)\]$/.exec(piece);
    if (pageMatch) {
      const page = Number(pageMatch[1]);
      const citation = citations.find((item) => item.page_number === page);
      if (!citation) {
        return (
          <span key={index} className="text-faint">
            {piece}
          </span>
        );
      }
      const isOpen = openPages.has(page);
      return (
        <button
          key={index}
          type="button"
          onClick={() => onTogglePage(page)}
          aria-expanded={isOpen}
          aria-label={`${isOpen ? "Hide" : "Show"} source from page ${page}`}
          title="Open the matching source excerpt"
          className={`mx-0.5 inline-flex translate-y-[-1px] items-center rounded-full border px-1.5 py-px align-baseline text-[10px] font-semibold transition-colors ${
            isOpen
              ? "border-brass-400/60 bg-brass-400/20 text-brass-300"
              : "border-brass-400/25 bg-brass-400/[0.08] text-brass-300 hover:border-brass-400/45 hover:bg-brass-400/15"
          }`}
        >
          [Page {page}]
        </button>
      );
    }

    if (piece.startsWith("**") && piece.endsWith("**") && piece.length > 4) {
      return (
        <strong key={index} className="font-semibold text-ink">
          {piece.slice(2, -2)}
        </strong>
      );
    }

    return <span key={index}>{piece}</span>;
  });
}

function AnswerBody({
  message,
  openPages,
  onTogglePage,
}: {
  message: ChatEntry;
  openPages: Set<number>;
  onTogglePage: (page: number) => void;
}) {
  const lines = message.content.split("\n");

  return (
    <div className="space-y-1">
      {lines.map((line, index) => {
        if (!line.trim()) {
          return <div key={index} className="h-2" aria-hidden="true" />;
        }
        const isBullet = /^\s*[-*]\s+/.test(line);
        const isQuote = /^\s*>\s+/.test(line);
        const text = isQuote
          ? line.replace(/^\s*>\s+/, "")
          : isBullet
            ? line.replace(/^\s*[-*]\s+/, "")
            : line;
        return (
          <p
            key={index}
            className={`text-[13.5px] leading-[1.75] text-[#c9d3e0] ${
              isBullet ? "flex gap-2.5 pl-0.5" : ""
            } ${isQuote ? "border-l-2 border-brass-400/35 pl-3 italic text-muted" : ""}`}
          >
            {isBullet ? (
              <span
                className="mt-[9px] size-1 shrink-0 rounded-full bg-brass-400/80"
                aria-hidden="true"
              />
            ) : null}
            <span className="min-w-0">
              {renderInline(text, message.citations, openPages, onTogglePage)}
            </span>
          </p>
        );
      })}
    </div>
  );
}

export function ChatMessageBubble({ message }: { message: ChatEntry }) {
  const [openPages, setOpenPages] = useState<Set<number>>(new Set());

  const togglePage = (page: number) => {
    setOpenPages((current) => {
      const next = new Set(current);
      if (next.has(page)) next.delete(page);
      else next.add(page);
      return next;
    });
  };

  if (message.role === "user") {
    return (
      <div className="animate-rise flex justify-end">
        <div className="flex max-w-[88%] flex-col items-end gap-1 sm:max-w-[78%]">
          <span className="pr-1 text-[9px] font-medium uppercase tracking-[0.16em] text-faint">
            You
          </span>
          <div className="whitespace-pre-wrap rounded-panel rounded-tr-sm border border-brass-400/20 bg-brass-400/[0.08] px-4 py-2.5 text-[13px] leading-relaxed text-[#ecdfcd]">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  const expanded = message.citations.filter(
    (citation, index) =>
      openPages.has(citation.page_number) &&
      message.citations.findIndex(
        (candidate) => candidate.page_number === citation.page_number,
      ) === index,
  );

  return (
    <article className="animate-rise flex gap-3">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border border-line bg-panel-raised text-brass-300">
        <Sparkles size={14} strokeWidth={1.8} aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex flex-wrap items-center gap-2">
          <span className="font-display text-sm leading-none text-ink">LecturaRAG</span>
          <span className="rounded-full border border-line px-1.5 py-px text-[9px] uppercase tracking-wider text-faint">
            {message.fallback_used ? "Local engine" : "LLM"}
          </span>
          {message.citations.length > 0 ? (
            <span className="text-[10px] text-faint">
              {message.citations.length} retrieved {message.citations.length === 1 ? "chunk" : "chunks"}
            </span>
          ) : null}
        </div>

        <div className="rounded-panel border border-line-soft bg-panel/60 px-4 py-3.5">
          <AnswerBody message={message} openPages={openPages} onTogglePage={togglePage} />

          {expanded.length > 0 ? (
            <div className="mt-3 space-y-2 border-t border-line-soft pt-3">
              {expanded.map((citation) => {
                const fullSource = message.sources?.find(
                  (source) =>
                    source.page_number === citation.page_number &&
                    source.chunk_index === citation.chunk_index,
                )?.content;
                return (
                  <div
                    key={citation.page_number}
                    className="animate-fade rounded-lg border border-brass-400/15 bg-brass-400/[0.035] px-3 py-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <PageStamp page={citation.page_number} />
                      <span className="text-[9px] uppercase tracking-wider text-faint">
                        {Math.round(citation.similarity * 100)}% match
                      </span>
                    </div>
                    <div className="scrollbar-slim mt-2 max-h-40 overflow-y-auto">
                      <p className="whitespace-pre-wrap text-[11.5px] leading-relaxed text-muted">
                        {fullSource ?? citation.snippet}
                      </p>
                    </div>
                    <p className="mt-2 flex items-center gap-1 text-[9px] uppercase tracking-wider text-faint">
                      <Quote size={9} aria-hidden="true" />
                      Indexed chunk {citation.chunk_index} · page {citation.page_number}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : message.citations.length > 0 ? (
            <p className="mt-2.5 text-[10px] text-faint">
              Tap a page badge to read the exact source excerpt.
            </p>
          ) : null}
        </div>
      </div>
    </article>
  );
}
