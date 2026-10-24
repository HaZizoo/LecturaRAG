import { ArrowLeft, Check, RotateCcw, Trophy, X } from "lucide-react";
import type {
  AnswerCheck,
  Quiz,
  QuizAttempt,
  QuizQuestionResult,
} from "../lib/types";
import { ErrorNotice, PageStamp, ghostButton, primaryButton, secondaryButton } from "./ui";

interface QuizResultsProps {
  quiz: Quiz;
  attempt: QuizAttempt | null;
  checks: (AnswerCheck | null)[];
  answers: (number | null)[];
  score: number;
  persistError: string | null;
  onRestart: () => void;
  onExit: () => void;
}

export function QuizResults({
  quiz,
  attempt,
  checks,
  answers,
  score,
  persistError,
  onRestart,
  onExit,
}: QuizResultsProps) {
  const localResults: QuizQuestionResult[] = quiz.questions.map((question, index) => {
    const check = checks[index];
    return {
      question_id: question.id,
      order_index: question.order_index,
      question: question.question,
      options: question.options,
      selected_index: answers[index] ?? null,
      correct_index: check?.correct_index ?? -1,
      is_correct: check?.is_correct ?? false,
      explanation: check?.explanation ?? "No explanation was returned for this question.",
      source_page: check?.source_page ?? question.source_page,
    };
  });

  const results = attempt?.results ?? localResults;
  const total = attempt?.total ?? quiz.questions.length;
  const finalScore = attempt?.score ?? score;
  const percentage = attempt?.percentage ?? (total ? Math.round((finalScore / total) * 100) : 0);
  const headline =
    percentage >= 85
      ? "Excellent recall."
      : percentage >= 60
        ? "A solid foundation."
        : "Worth another pass.";

  return (
    <section className="h-full overflow-y-auto scrollbar-slim">
      <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
        <div className="flex items-center justify-between gap-3">
          <button type="button" onClick={onExit} className={ghostButton}>
            <ArrowLeft size={14} aria-hidden="true" />
            Quiz overview
          </button>
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
            Quiz complete
          </span>
        </div>

        <div className="mt-4 rounded-card border border-line bg-gradient-to-br from-[#12202a] via-panel to-panel p-6 sm:p-8">
          <div className="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-jade">
                <Trophy size={12} aria-hidden="true" />
                Attempt recorded
              </span>
              <h2 className="mt-2 font-display text-3xl leading-tight text-ink">{headline}</h2>
              <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted">
                {finalScore} of {total} correct on {quiz.questions.length} generated questions.
                Review the explanations below, then retry the deck when you are ready.
              </p>
            </div>

            <div
              className="relative flex size-36 shrink-0 items-center justify-center rounded-full"
              style={{
                background: `conic-gradient(var(--color-brass-400) ${
                  percentage * 3.6
                }deg, var(--color-line-soft) 0deg)`,
              }}
              role="img"
              aria-label={`Score: ${percentage} percent, ${finalScore} of ${total} correct`}
            >
              <div className="absolute inset-[6px] rounded-full bg-panel" />
              <div className="relative text-center">
                <p className="font-display text-3xl leading-none text-ink">{percentage}%</p>
                <p className="mt-1.5 text-[9px] uppercase tracking-[0.14em] text-faint">
                  {finalScore} / {total} correct
                </p>
              </div>
            </div>
          </div>

          {persistError ? (
            <div className="mt-5">
              <ErrorNotice
                message={`Your score is shown below, but the attempt could not be saved. ${persistError}`}
                compact
              />
            </div>
          ) : null}

          <div className="mt-6 flex flex-wrap gap-2">
            <button type="button" className={primaryButton} onClick={onRestart}>
              <RotateCcw size={14} aria-hidden="true" />
              Try again
            </button>
            <button type="button" className={secondaryButton} onClick={onExit}>
              Back to overview
            </button>
          </div>
        </div>

        <div className="mt-7">
          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-faint">
                Answer review
              </p>
              <h3 className="mt-1.5 font-display text-2xl text-ink">Review the misses.</h3>
            </div>
            <span className="text-[10px] text-faint">
              {results.filter((result) => result.is_correct).length} correct
            </span>
          </div>

          <ol className="mt-4 space-y-2.5">
            {results.map((result, index) => {
              const selectedOption =
                result.selected_index !== null ? result.options[result.selected_index] : null;
              const correctOption =
                result.correct_index >= 0 ? result.options[result.correct_index] : null;

              return (
                <li
                  key={result.question_id}
                  className="rounded-panel border border-line-soft bg-panel/55 px-4 py-4"
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border ${
                        result.is_correct
                          ? "border-jade/25 bg-jade/10 text-jade"
                          : "border-rose/25 bg-rose/10 text-rose"
                      }`}
                    >
                      {result.is_correct ? (
                        <Check size={13} aria-hidden="true" />
                      ) : (
                        <X size={13} aria-hidden="true" />
                      )}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-faint">
                          Question {index + 1}
                        </span>
                        <PageStamp page={result.source_page} />
                      </div>
                      <p className="mt-1.5 text-[13px] font-medium leading-snug text-ink">
                        {result.question}
                      </p>

                      <div className="mt-2.5 space-y-1 text-[11.5px] leading-relaxed">
                        <p className={result.is_correct ? "text-jade" : "text-rose"}>
                          <span className="text-faint">Your answer: </span>
                          {selectedOption ?? "No answer"}
                        </p>
                        {!result.is_correct && correctOption ? (
                          <p className="text-jade">
                            <span className="text-faint">Correct answer: </span>
                            {correctOption}
                          </p>
                        ) : null}
                      </div>

                      <p className="mt-2 text-[11.5px] leading-relaxed text-faint">
                        {result.explanation}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
