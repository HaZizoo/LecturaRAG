import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  Clock3,
  Loader2,
  X,
} from "lucide-react";
import { api, getErrorMessage } from "../lib/api";
import type { AnswerCheck, Quiz, QuizAttempt } from "../lib/types";
import { QuizResults } from "./QuizResults";
import { ErrorNotice, PageStamp, ghostButton, primaryButton } from "./ui";

const SECONDS_PER_QUESTION = 30;

interface QuizSessionProps {
  quiz: Quiz;
  isActive: boolean;
  onExit: () => void;
  onRestart: () => void;
}

export function QuizSession({ quiz, isActive, onExit, onRestart }: QuizSessionProps) {
  const total = quiz.questions.length;
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>(() =>
    quiz.questions.map(() => null),
  );
  const [checks, setChecks] = useState<(AnswerCheck | null)[]>(() =>
    quiz.questions.map(() => null),
  );
  const [selected, setSelected] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [score, setScore] = useState(0);
  const [timeLeft, setTimeLeft] = useState(SECONDS_PER_QUESTION);
  const [finished, setFinished] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timeoutFired = useRef(false);
  const checkingRef = useRef(false);

  const current = quiz.questions[index];
  const currentCheck = checks[index];

  const reveal = useCallback(
    async (choice: number | null) => {
      // The timer and a click can fire in the same tick; guard synchronously
      // so a question is never submitted twice (double score / wrong answer).
      if (!current || revealed || isChecking || checkingRef.current || finished) return;
      checkingRef.current = true;
      setIsChecking(true);
      setError(null);
      setSelected(choice);

      try {
        const result = await api.checkAnswer(quiz.id, current.id, choice);
        setChecks((previous) => {
          const next = [...previous];
          next[index] = result;
          return next;
        });
        setAnswers((previous) => {
          const next = [...previous];
          next[index] = choice;
          return next;
        });
        if (result.is_correct) setScore((value) => value + 1);
        setRevealed(true);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        checkingRef.current = false;
        setIsChecking(false);
      }
    },
    [current, finished, index, isChecking, quiz.id, revealed],
  );

  useEffect(() => {
    setTimeLeft(SECONDS_PER_QUESTION);
    timeoutFired.current = false;
  }, [index]);

  useEffect(() => {
    if (!isActive || revealed || finished || isChecking) return;
    if (timeLeft <= 0) {
      if (!timeoutFired.current) {
        timeoutFired.current = true;
        void reveal(null);
      }
      return;
    }
    const timer = window.setTimeout(() => {
      setTimeLeft((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [finished, isActive, isChecking, revealed, reveal, timeLeft]);

  const finish = useCallback(async () => {
    if (isSubmitting || finished) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await api.submitQuizAttempt(quiz.id, answers);
      setAttempt(result);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
      setFinished(true);
    }
  }, [answers, finished, isSubmitting, quiz.id]);

  const next = () => {
    if (!revealed || isSubmitting) return;
    setError(null);
    if (index + 1 >= total) {
      void finish();
      return;
    }
    setIndex((value) => value + 1);
    setSelected(null);
    setRevealed(false);
  };

  if (finished) {
    return (
      <QuizResults
        quiz={quiz}
        attempt={attempt}
        checks={checks}
        answers={answers}
        score={score}
        persistError={attempt === null ? error : null}
        onRestart={onRestart}
        onExit={onExit}
      />
    );
  }

  const timerTone =
    timeLeft <= 5
      ? "border-rose/30 bg-rose/[0.07] text-rose"
      : timeLeft <= 10
        ? "border-amber/30 bg-amber/[0.06] text-amber"
        : "border-line bg-panel text-muted";

  return (
    <section className="h-full overflow-y-auto scrollbar-slim">
      <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="flex items-center justify-between gap-3">
          <button type="button" onClick={onExit} className={ghostButton}>
            <X size={14} aria-hidden="true" />
            Exit quiz
          </button>
          <div className="flex items-center gap-3 text-[11px] text-muted">
            <span>
              Question <strong className="font-semibold text-ink">{index + 1}</strong> / {total}
            </span>
            <span aria-hidden="true" className="size-0.5 rounded-full bg-line" />
            <span>
              Score <strong className="font-semibold text-ink">{score}</strong>
            </span>
            <span className="sr-only" aria-live="polite">
              Score {score} of {total}
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
            {quiz.title}
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold tabular-nums ${timerTone}`}
            aria-live="off"
          >
            <Clock3 size={12} aria-hidden="true" />
            {timeLeft}s
          </span>
        </div>

        <div className="mt-2 flex gap-1" aria-hidden="true">
          {quiz.questions.map((question, questionIndex) => {
            const check = checks[questionIndex];
            return (
              <span
                key={question.id}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  check?.is_correct
                    ? "bg-jade"
                    : check
                      ? "bg-rose"
                      : questionIndex === index
                        ? "bg-brass-400"
                        : "bg-line"
                }`}
              />
            );
          })}
        </div>

        <div className="mt-5 rounded-card border border-line bg-gradient-to-b from-panel-raised to-panel p-5 sm:p-7">
          <p className="text-[10px] uppercase tracking-[0.16em] text-faint">
            Multiple choice · choose one
          </p>
          <h2 className="mt-2 text-balance font-display text-xl leading-snug text-ink sm:text-2xl">
            {current.question}
          </h2>

          <div
            className="mt-6 grid gap-2"
            role="radiogroup"
            aria-label="Answer options"
            aria-busy={isChecking}
          >
            {current.options.map((option, optionIndex) => {
              const isCorrectOption =
                revealed && currentCheck?.correct_index === optionIndex;
              const isWrongPick =
                revealed &&
                currentCheck !== null &&
                selected === optionIndex &&
                !currentCheck.is_correct;
              const isPicked = !revealed && selected === optionIndex;

              return (
                <button
                  key={option}
                  type="button"
                  role="radio"
                  aria-checked={selected === optionIndex}
                  disabled={revealed || isChecking}
                  onClick={() => void reveal(optionIndex)}
                  className={`group flex w-full items-start gap-3 rounded-lg border px-3.5 py-3 text-left transition-colors ${
                    isCorrectOption
                      ? "border-jade/45 bg-jade/[0.07]"
                      : isWrongPick
                        ? "border-rose/45 bg-rose/[0.07]"
                        : isPicked
                          ? "border-brass-400/45 bg-brass-400/[0.07]"
                          : "border-line-soft bg-white/[0.012] hover:border-brass-400/25 hover:bg-white/[0.03]"
                  } ${revealed ? "cursor-default" : ""}`}
                >
                  <span
                    className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded border text-[10px] font-semibold ${
                      isCorrectOption
                        ? "border-jade/40 bg-jade/10 text-jade"
                        : isWrongPick
                          ? "border-rose/40 bg-rose/10 text-rose"
                          : isPicked
                            ? "border-brass-400/40 bg-brass-400/10 text-brass-300"
                            : "border-line bg-panel text-faint"
                    }`}
                  >
                    {String.fromCharCode(65 + optionIndex)}
                  </span>
                  <span className="min-w-0 flex-1 text-[13px] leading-relaxed text-[#ccd6e2]">
                    {option}
                  </span>
                  {isCorrectOption ? (
                    <Check size={16} className="mt-0.5 shrink-0 text-jade" aria-label="Correct" />
                  ) : isWrongPick ? (
                    <X size={16} className="mt-0.5 shrink-0 text-rose" aria-label="Incorrect" />
                  ) : null}
                </button>
              );
            })}
          </div>

          {isChecking ? (
            <p className="mt-4 flex items-center gap-2 text-[11px] text-faint" role="status">
              <Loader2 size={13} className="animate-spin" aria-hidden="true" />
              Checking your answer…
            </p>
          ) : null}
        </div>

        {error ? (
          <div className="mt-3">
            <ErrorNotice
              message={error}
              onRetry={revealed ? undefined : () => void reveal(selected)}
              compact
            />
          </div>
        ) : null}

        {revealed && currentCheck ? (
          <div
            role="status"
            aria-live="polite"
            className={`animate-rise mt-4 rounded-panel border px-4 py-4 ${
              currentCheck.is_correct
                ? "border-jade/20 bg-jade/[0.035]"
                : "border-rose/20 bg-rose/[0.03]"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span
                className={`inline-flex items-center gap-2 text-sm font-semibold ${
                  currentCheck.is_correct ? "text-jade" : "text-rose"
                }`}
              >
                {currentCheck.is_correct ? (
                  <Check size={15} aria-hidden="true" />
                ) : (
                  <X size={15} aria-hidden="true" />
                )}
                {currentCheck.is_correct
                  ? "Correct"
                  : selected === null
                    ? "Time's up"
                    : "Not quite"}
              </span>
              <PageStamp page={currentCheck.source_page} />
            </div>
            <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
              {currentCheck.explanation}
            </p>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={next}
                disabled={isSubmitting}
                className={primaryButton}
              >
                {isSubmitting ? (
                  <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                ) : null}
                {isSubmitting
                  ? "Saving results…"
                  : index + 1 >= total
                    ? "See results"
                    : "Next question"}
                {!isSubmitting ? <ArrowRight size={14} aria-hidden="true" /> : null}
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
