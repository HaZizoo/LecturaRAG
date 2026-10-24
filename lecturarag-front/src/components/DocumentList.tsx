import { FileText, Library, Loader2, RefreshCw, Trash2 } from "lucide-react";
import type { DocumentSummary } from "../lib/types";
import { ErrorNotice, SkeletonBlock, iconButton } from "./ui";

interface DocumentListProps {
  documents: DocumentSummary[];
  selectedId: string | null;
  isLoading: boolean;
  error: string | null;
  deletingId: string | null;
  onSelect: (documentId: string) => void;
  onDelete: (document: DocumentSummary) => void;
  onRetry: () => void;
}

export function DocumentList({
  documents,
  selectedId,
  isLoading,
  error,
  deletingId,
  onSelect,
  onDelete,
  onRetry,
}: DocumentListProps) {
  return (
    <section aria-labelledby="library-heading" className="mt-7">
      <div className="mb-2 flex items-center justify-between px-1">
        <h2
          id="library-heading"
          className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-faint"
        >
          <Library size={12} aria-hidden="true" />
          Library
          {documents.length > 0 ? (
            <span className="rounded-full border border-line px-1.5 py-px text-[9px] tracking-normal text-muted">
              {documents.length}
            </span>
          ) : null}
        </h2>
        <button
          type="button"
          className={iconButton}
          onClick={onRetry}
          aria-label="Refresh document library"
          title="Refresh library"
        >
          <RefreshCw size={13} aria-hidden="true" />
        </button>
      </div>

      {error ? (
        <div className="mb-2">
          <ErrorNotice message={error} onRetry={onRetry} compact />
        </div>
      ) : null}

      {isLoading ? (
        <div className="space-y-2" aria-busy="true" aria-label="Loading documents">
          <SkeletonBlock className="h-[58px]" />
          <SkeletonBlock className="h-[58px]" />
          <SkeletonBlock className="h-[58px]" />
        </div>
      ) : documents.length === 0 ? (
        <div className="rounded-panel border border-line-soft bg-white/[0.015] px-4 py-5 text-center">
          <FileText size={18} className="mx-auto text-faint" aria-hidden="true" />
          <p className="mt-2 text-xs font-medium text-muted">No lectures yet</p>
          <p className="mt-1 text-[11px] leading-relaxed text-faint">
            Upload a PDF or Markdown file to build your workspace.
          </p>
        </div>
      ) : (
        <ul className="space-y-1.5">
          {documents.map((document) => {
            const isSelected = document.id === selectedId;
            const isDeleting = document.id === deletingId;
            return (
              <li key={document.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(document.id)}
                  aria-current={isSelected ? "true" : undefined}
                  className={`w-full rounded-panel border px-3 py-2.5 pr-9 text-left transition-colors ${
                    isSelected
                      ? "border-brass-400/35 bg-brass-400/[0.07]"
                      : "border-transparent hover:border-line hover:bg-white/[0.025]"
                  }`}
                >
                  <span className="flex items-start gap-2.5">
                    <span
                      className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md border ${
                        isSelected
                          ? "border-brass-400/30 bg-brass-400/10 text-brass-300"
                          : "border-line bg-panel-raised text-faint"
                      }`}
                    >
                      <FileText size={13} aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12.5px] font-medium leading-snug text-ink">
                        {document.title}
                      </span>
                      <span className="mt-1 block text-[10px] text-faint">
                        {document.page_count} pages · {document.chunk_count} chunks
                      </span>
                    </span>
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => onDelete(document)}
                  disabled={isDeleting}
                  aria-label={`Delete ${document.title}`}
                  title="Delete document"
                  className={`absolute right-2 top-2.5 inline-flex size-6 items-center justify-center rounded text-faint transition-all hover:bg-rose/10 hover:text-rose ${
                    isSelected ? "opacity-100" : "opacity-0 focus:opacity-100 group-hover:opacity-100"
                  }`}
                >
                  {isDeleting ? (
                    <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                  ) : (
                    <Trash2 size={12} aria-hidden="true" />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
