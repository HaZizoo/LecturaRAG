import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Layers3,
  Loader2,
  RefreshCw,
  RotateCcw,
  RotateCw,
} from "lucide-react";
import type { CardStatus, Deck, Difficulty, DocumentSummary } from "../lib/types";
import { FlashcardStage } from "./FlashcardStage";
import {
  EmptyPanel,
  ErrorNotice,
  SkeletonBlock,
  ghostButton,
  primaryButton,
  secondaryButton,
} from "./ui";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "easy", label: "Easy" },
  { id: "medium", label: "Medium" },
  { id: "hard", label: "Hard" },
] as const;

type Filter = (typeof FILTERS)[number]["id"];

interface FlashcardsPanelProps {
  document: DocumentSummary;
  deck: Deck | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;
  statusError: string | null;
  isActive: boolean;
  onGenerate: (count?: number) => Promise<boolean>;
  onSetStatus: (cardId: string, status: CardStatus) => Promise<boolean>;
  onReload: () => void;
}

export function FlashcardsPanel({
  document,
  deck,
  isLoading,
  isGenerating,
  error,
  statusError,
  isActive,
  onGenerate,
  onSetStatus,
  onReload,
}: FlashcardsPanelProps) {
  const [filter, setFilter] = useState<Filter>("all");
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  const cards = useMemo(
    () => (deck ? [...deck.cards].sort((a, b) => a.order_index - b.order_index) : []),
    [deck],
  );
  const filteredCards = useMemo(
    () => (filter === "all" ? cards : cards.filter((card) => card.difficulty === filter)),
    [cards, filter],
  );

  useEffect(() => {
    setIndex(0);
    setFlipped(false);
  }, [deck?.id, filter]);

  useEffect(() => {
    if (index > Math.max(0, filteredCards.length - 1)) setIndex(0);
  }, [filteredCards.length, index]);

  useEffect(() => {
    if (!isActive || !deck || filteredCards.length === 0) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.code !== "Space" || event.repeat) return;
      const target = event.target as HTMLElement | null;
      if (
        target?.isContentEditable ||
        target?.closest("button, a, input, textarea, select, [role='textbox']")
      ) {
        return;
      }
      event.preventDefault();
      setFlipped((current) => !current);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isActive, deck, filteredCards.length]);

  const current = filteredCards[index] ?? null;
  const masteredCount = cards.filter((card) => card.status === "mastered").length;
  const progress = cards.length > 0 ? Math.round((masteredCount / cards.length) * 100) : 0;

  const move = (direction: 1 | -1) => {
    if (filteredCards.length === 0) return;
    setFlipped(false);
    setIndex((currentIndex) => {
      const next = currentIndex + direction;
      if (next < 0) return filteredCards.length - 1;
      if (next >= filteredCards.length) return 0;
      return next;
    });
  };

  const mark = async (status: CardStatus) => {
    if (!current) return;
    const updated = await onSetStatus(current.id, status);
    if (updated) {
      setFlipped(false);
      move(1);
    }
  };

  const countFor = (value: Difficulty) =>
    cards.filter((card) => card.difficulty === value).length;

  if (isLoading) {
    return (
      <section className="h-full overflow-y-auto scrollbar-slim" aria-busy="true">
        <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6">
          <SkeletonBlock className="h-10 w-56" />
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <SkeletonBlock className="h-9" />
            <SkeletonBlock className="h-9" />
          </div>
          <SkeletonBlock className="mt-6 h-[390px]" />
        </div>
      </section>
    );
  }

  if (!deck) {
    return (
      <section className="h-full overflow-y-auto scrollbar-slim">
        {error ? (
          <div className="mx-auto max-w-xl px-4 pt-6">
            <ErrorNotice message={error} onRetry={onReload} />
          </div>
        ) : null}
        <EmptyPanel
          icon={Layers3}
          title="Build a deck from this lecture"
          description={`Generate 12 cited flashcards from ${document.title}. Flip each card, then mark what you have mastered.`}
        >
          <button
            type="button"
            className={primaryButton}
            disabled={isGenerating}
            onClick={() => void onGenerate(12)}
          >
            {isGenerating ? (
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
            ) : (
              <Layers3 size={15} aria-hidden="true" />
            )}
            {isGenerating ? "Generating deck…" : "Generate 12 cards"}
          </button>
        </EmptyPanel>
      </section>
    );
  }

  return (
    <section className="h-full overflow-y-auto scrollbar-slim">
      <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
              Study deck
            </p>
            <h2 className="mt-1.5 font-display text-2xl text-ink">Recall, don&apos;t reread.</h2>
            <p className="mt-1 text-[11px] text-faint">
              {cards.length} cards · {cards.filter((card) => card.status === "needs_review").length}{" "}
              marked for review
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onGenerate(12)}
            disabled={isGenerating}
            className={secondaryButton}
          >
            {isGenerating ? (
              <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw size={14} aria-hidden="true" />
            )}
            {isGenerating ? "Building…" : "New deck"}
          </button>
        </div>

        {error ? (
          <div className="mt-4">
            <ErrorNotice
              message={error}
              onRetry={() => void onGenerate(12)}
              compact
            />
          </div>
        ) : null}

        <div className="mt-5">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-muted">
              <strong className="font-semibold text-ink">{masteredCount}</strong> of {cards.length}{" "}
              mastered
            </span>
            <span className="text-faint">{progress}%</span>
          </div>
          <div
            className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line-soft"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label="Flashcards mastered"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-brass-500 to-brass-300 transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-1.5">
          {FILTERS.map((item) => {
            const count = item.id === "all" ? cards.length : countFor(item.id);
            const active = filter === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setFilter(item.id)}
                aria-pressed={active}
                className={`rounded-full border px-3 py-1 text-[11px] font-medium transition-colors ${
                  active
                    ? "border-brass-400/40 bg-brass-400/10 text-brass-300"
                    : "border-line-soft text-faint hover:border-line hover:text-muted"
                }`}
              >
                {item.label}
                <span className="ml-1.5 text-[9px] opacity-70">{count}</span>
              </button>
            );
          })}
        </div>

        {statusError ? (
          <div className="mt-3">
            <ErrorNotice message={statusError} compact />
          </div>
        ) : null}

        {current ? (
          <>
            <div className="mt-5">
              <FlashcardStage
                card={current}
                flipped={flipped}
                onFlip={() => setFlipped((value) => !value)}
              />
            </div>

            <div className="mt-3 flex items-center justify-between">
              <button
                type="button"
                onClick={() => move(-1)}
                className={ghostButton}
                aria-label="Previous card"
              >
                <ChevronLeft size={15} aria-hidden="true" />
                Previous
              </button>
              <div className="flex items-center gap-3">
                <span className="text-[10px] tabular-nums text-faint">
                  {index + 1} / {filteredCards.length}
                </span>
                <button
                  type="button"
                  onClick={() => setFlipped((value) => !value)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-[10px] font-medium text-muted hover:border-brass-400/30 hover:text-ink"
                >
                  <RotateCw size={11} aria-hidden="true" />
                  Flip
                </button>
              </div>
              <button
                type="button"
                onClick={() => move(1)}
                className={ghostButton}
                aria-label="Next card"
              >
                Next
                <ChevronRight size={15} aria-hidden="true" />
              </button>
            </div>

            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => void mark("needs_review")}
                className={`inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-3 text-xs font-semibold transition-colors ${
                  current.status === "needs_review"
                    ? "border-amber/40 bg-amber/10 text-amber"
                    : "border-amber/20 bg-amber/[0.04] text-amber hover:border-amber/40 hover:bg-amber/[0.09]"
                }`}
              >
                <RotateCcw size={14} aria-hidden="true" />
                Review again
              </button>
              <button
                type="button"
                onClick={() => void mark("mastered")}
                className={`inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-3 text-xs font-semibold transition-colors ${
                  current.status === "mastered"
                    ? "border-jade/40 bg-jade/10 text-jade"
                    : "border-jade/20 bg-jade/[0.04] text-jade hover:border-jade/40 hover:bg-jade/[0.09]"
                }`}
              >
                <Check size={14} aria-hidden="true" />
                Mastered
              </button>
            </div>

            <p className="mt-2 text-center text-[10px] text-faint">
              Progress is saved to your deck. Space flips the card; the status buttons advance to
              the next one.
            </p>
          </>
        ) : (
          <div className="mt-6 rounded-panel border border-line-soft bg-white/[0.015] px-4 py-10 text-center">
            <p className="text-sm font-medium text-muted">No {filter} cards in this deck</p>
            <p className="mt-1 text-[11px] text-faint">Switch the filter or regenerate the deck.</p>
          </div>
        )}
      </div>
    </section>
  );
}
