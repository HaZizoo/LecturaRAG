import { BookOpen, Layers3, MessageSquareText, Timer } from "lucide-react";
import { ErrorNotice, SkeletonBlock } from "./ui";
import { UploadZone } from "./UploadZone";

const FEATURES = [
  { icon: MessageSquareText, label: "Cited chat" },
  { icon: Layers3, label: "3D flashcards" },
  { icon: Timer, label: "Timed quizzes" },
];

interface WorkspaceEmptyProps {
  isLoading: boolean;
  listError: string | null;
  uploading: boolean;
  uploadError: string | null;
  onUpload: (file: File) => Promise<boolean>;
  onClearUploadError: () => void;
  onRetry: () => void;
}

export function WorkspaceEmpty({
  isLoading,
  listError,
  uploading,
  uploadError,
  onUpload,
  onClearUploadError,
  onRetry,
}: WorkspaceEmptyProps) {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center px-4" aria-busy="true">
        <div className="w-full max-w-md space-y-3">
          <SkeletonBlock className="h-12" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-32" />
        </div>
      </div>
    );
  }

  return (
    <div className="scrollbar-slim h-full overflow-y-auto">
      <div className="mx-auto flex min-h-full w-full max-w-lg flex-col justify-center px-4 py-10 sm:px-6">
        <div className="animate-rise">
          <span className="inline-flex size-12 items-center justify-center rounded-panel border border-brass-400/25 bg-brass-400/[0.06] text-brass-300">
            <BookOpen size={22} strokeWidth={1.7} aria-hidden="true" />
          </span>
          <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.18em] text-brass-400">
            LecturaRAG workspace
          </p>
          <h2 className="mt-2 text-balance font-display text-4xl leading-[1.1] text-ink">
            Your lectures, made <span className="italic text-brass-300">interrogable.</span>
          </h2>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-muted">
            Drop in a PDF or Markdown lecture. LecturaRAG indexes every page, answers with exact
            citations, and turns the material into flashcards and timed quizzes.
          </p>

          <div className="mt-7">
            <UploadZone
              uploading={uploading}
              serverError={uploadError}
              onUpload={onUpload}
              onClearServerError={onClearUploadError}
            />
          </div>

          {listError ? (
            <div className="mt-3">
              <ErrorNotice message={listError} onRetry={onRetry} compact />
            </div>
          ) : null}

          <div className="mt-7 grid grid-cols-3 divide-x divide-line-soft border-y border-line-soft py-3">
            {FEATURES.map((feature) => {
              const Icon = feature.icon;
              return (
                <div key={feature.label} className="flex flex-col items-center gap-1.5 px-2">
                  <Icon size={15} className="text-brass-300" strokeWidth={1.7} aria-hidden="true" />
                  <span className="text-[10px] text-faint">{feature.label}</span>
                </div>
              );
            })}
          </div>

          <p className="mt-3 text-[10px] leading-relaxed text-faint">
            No API key? The deterministic engine still builds cited answers, decks, and quizzes
            from the pages you upload.
          </p>
        </div>
      </div>
    </div>
  );
}
