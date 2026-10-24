import { useEffect, useState } from "react";
import { ListChecks, Loader2, RefreshCw, Timer, Trophy, Zap } from "lucide-react";
import type { DocumentSummary, Quiz } from "../lib/types";
import { QuizSession } from "./QuizSession";
import {
  EmptyPanel,
  ErrorNotice,
  SkeletonBlock,
  ghostButton,
  primaryButton,
  secondaryButton,
} from "./ui";

interface QuizPanelProps {
  document: DocumentSummary;
  quiz: Quiz | null;
  isLoading: boolean;
  isGenerating: boolean;
  error: string | null;
  isActive: boolean;
  onGenerate: (count?: number) => Promise<boolean>;
  onReload: () => void;
}

export function QuizPanel({
  document,
  quiz,
  isLoading,
  isGenerating,
  error,
  isActive,
  onGenerate,
  onReload,
}: QuizPanelProps) {
  const [playing, setPlaying] = useState(false);
  const [round, setRound] = useState(0);

  useEffect(() => {
    setPlaying(false);
    setRound(0);
  }, [quiz?.id]);

  if (isLoading) {
    return (
      <section className="h-full overflow-y-auto scrollbar-slim" aria-busy="true">
        <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6">
          <SkeletonBlock className="h-10 w-52" />
          <SkeletonBlock className="mt-6 h-[340px]" />
        </div>
      </section>
    );
  }

  if (!quiz) {
    return (
      <section className="h-full overflow-y-auto scrollbar-slim">
        {error ? (
          <div className="mx-auto max-w-xl px-4 pt-6">
            <ErrorNotice message={error} onRetry={onReload} />
          </div>
        ) : null}
        <EmptyPanel
          icon={ListChecks}
          title="Turn this lecture into an exam"
          description={`Generate a multiple-choice quiz from ${document.title}, with instant validation and page-cited explanations.`}
        >
          <button
            type="button"
            className={primaryButton}
            disabled={isGenerating}
            onClick={() => void onGenerate(6)}
          >
            {isGenerating ? (
              <Loader2 size={15} className="animate-spin" aria-hidden="true" />
            ) : (
              <ListChecks size={15} aria-hidden="true" />
            )}
            {isGenerating ? "Writing questions…" : "Generate a quiz"}
          </button>
        </EmptyPanel>
      </section>
    );
  }

  if (playing) {
    return (
      <QuizSession
        key={`${quiz.id}-${round}`}
        quiz={quiz}
        isActive={isActive}
        onExit={() => setPlaying(false)}
        onRestart={() => setRound((value) => value + 1)}
      />
    );
  }

  return (
    <section className="h-full overflow-y-auto scrollbar-slim">
      <div className="mx-auto w-full max-w-2xl px-4 py-8 sm:px-6 sm:py-12">
        <div className="rounded-card border border-line bg-gradient-to-br from-[#121a24] via-panel to-panel p-6 sm:p-8">
          <div className="flex size-12 items-center justify-center rounded-panel border border-brass-400/25 bg-brass-400/[0.07] text-brass-300">
            <Trophy size={22} strokeWidth={1.7} aria-hidden="true" />
          </div>
          <p className="mt-4 text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
            Timed quiz
          </p>
          <h2 className="mt-2 font-display text-3xl leading-tight text-ink">
            Test the lecture, under pressure.
          </h2>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-muted">
            {quiz.questions.length} multiple-choice questions drawn from{" "}
            <span className="text-ink">{document.title}</span>. Every answer is checked instantly
            and explained with its page.
          </p>

          <div className="mt-6 grid grid-cols-3 divide-x divide-line-soft rounded-panel border border-line-soft bg-black/10">
            <div className="px-3 py-3 text-center">
              <p className="font-display text-xl text-ink">{quiz.questions.length}</p>
              <p className="mt-0.5 text-[9px] uppercase tracking-wider text-faint">Questions</p>
            </div>
            <div className="px-3 py-3 text-center">
              <p className="flex items-center justify-center gap-1 font-display text-xl text-ink">
                <Timer size={14} className="text-brass-300" aria-hidden="true" />
                30s
              </p>
              <p className="mt-0.5 text-[9px] uppercase tracking-wider text-faint">Per question</p>
            </div>
            <div className="px-3 py-3 text-center">
              <p className="flex items-center justify-center gap-1 font-display text-xl text-ink">
                <Zap size={14} className="text-jade" aria-hidden="true" />
                Live
              </p>
              <p className="mt-0.5 text-[9px] uppercase tracking-wider text-faint">Feedback</p>
            </div>
          </div>

          {error ? (
            <div className="mt-4">
              <ErrorNotice message={error} onRetry={onReload} compact />
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <button type="button" className={primaryButton} onClick={() => setPlaying(true)}>
              <Trophy size={15} aria-hidden="true" />
              Start quiz
            </button>
            <button
              type="button"
              className={secondaryButton}
              disabled={isGenerating}
              onClick={() => {
                setPlaying(false);
                void onGenerate(6);
              }}
            >
              {isGenerating ? (
                <Loader2 size={14} className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw size={14} aria-hidden="true" />
              )}
              New quiz
            </button>
            <button type="button" className={ghostButton} onClick={onReload}>
              Reload
            </button>
          </div>
        </div>

        <p className="mt-4 text-center text-[10px] text-faint">
          Explanations cite the exact lecture page, so a wrong answer becomes a study note.
        </p>
      </div>
    </section>
  );
}
