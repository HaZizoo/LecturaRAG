import { RotateCw } from "lucide-react";
import type { Difficulty, Flashcard } from "../lib/types";
import { PageStamp } from "./ui";

const DIFFICULTY_STYLES: Record<Difficulty, { label: string; dot: string; pill: string }> = {
  easy: {
    label: "Easy",
    dot: "bg-jade",
    pill: "border-jade/20 bg-jade/[0.07] text-jade",
  },
  medium: {
    label: "Medium",
    dot: "bg-amber",
    pill: "border-amber/20 bg-amber/[0.07] text-amber",
  },
  hard: {
    label: "Hard",
    dot: "bg-rose",
    pill: "border-rose/20 bg-rose/[0.07] text-rose",
  },
};

interface FlashcardStageProps {
  card: Flashcard;
  flipped: boolean;
  onFlip: () => void;
}

export function FlashcardStage({ card, flipped, onFlip }: FlashcardStageProps) {
  const difficulty = DIFFICULTY_STYLES[card.difficulty];

  return (
    <button
      type="button"
      onClick={onFlip}
      data-flipped={flipped}
      aria-label={`${flipped ? "Answer" : "Question"}: ${flipped ? card.back : card.front} Activate to flip.`}
      className="flip-scene block w-full rounded-card text-left"
    >
      <div className="relative h-[350px] w-full sm:h-[390px] lg:h-[420px]">
        <div className="flip-inner">
          <div
            aria-hidden={flipped}
            className="flip-face flex flex-col rounded-card border border-line bg-gradient-to-br from-[#121b26] via-panel-raised to-panel p-6 sm:p-8"
          >
            <div className="flex items-center justify-between gap-3">
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${difficulty.pill}`}
              >
                <span className={`size-1 rounded-full ${difficulty.dot}`} aria-hidden="true" />
                {difficulty.label}
              </span>
              <PageStamp page={card.source_page} />
            </div>

            <div className="scrollbar-slim flex flex-1 items-center overflow-y-auto py-6">
              <p className="text-balance font-display text-[24px] leading-[1.35] text-ink sm:text-[28px] lg:text-[30px]">
                {card.front}
              </p>
            </div>

            <div className="flex items-center justify-between border-t border-line-soft pt-4">
              <span className="text-[10px] uppercase tracking-[0.16em] text-faint">
                Card {card.order_index + 1}
              </span>
              <span className="inline-flex items-center gap-1.5 text-[10px] text-muted">
                <RotateCw size={11} aria-hidden="true" />
                Click or press Space to reveal
              </span>
            </div>
          </div>

          <div
            aria-hidden={!flipped}
            className="flip-face flip-face-back flex flex-col rounded-card border border-brass-400/20 bg-gradient-to-br from-[#19140e] via-[#121821] to-panel p-6 sm:p-8"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-300">
                Answer
              </span>
              <PageStamp page={card.source_page} />
            </div>

            <div className="scrollbar-slim flex flex-1 items-center overflow-y-auto py-5">
              <p className="text-[15px] leading-[1.8] text-[#d4dde9] sm:text-base">{card.back}</p>
            </div>

            <div className="flex items-center justify-between border-t border-brass-400/15 pt-4">
              <span className="inline-flex items-center gap-1.5 text-[10px] text-brass-300/80">
                <RotateCw size={11} aria-hidden="true" />
                Flip back
              </span>
              <span className="text-[10px] uppercase tracking-[0.16em] text-faint">
                Page {card.source_page}
              </span>
            </div>
          </div>
        </div>
      </div>
    </button>
  );
}
