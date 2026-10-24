import { BookOpen, X } from "lucide-react";
import type { DocumentSummary, Health } from "../lib/types";
import { DocumentList } from "./DocumentList";
import { UploadZone } from "./UploadZone";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  documents: DocumentSummary[];
  selectedId: string | null;
  isLoading: boolean;
  error: string | null;
  uploading: boolean;
  uploadError: string | null;
  deletingId: string | null;
  health: Health | null;
  isOnline: boolean;
  onSelect: (documentId: string) => void;
  onUpload: (file: File) => Promise<boolean>;
  onClearUploadError: () => void;
  onDelete: (document: DocumentSummary) => void;
  onRefresh: () => void;
}

export function Sidebar({
  isOpen,
  onClose,
  documents,
  selectedId,
  isLoading,
  error,
  uploading,
  uploadError,
  deletingId,
  health,
  isOnline,
  onSelect,
  onUpload,
  onClearUploadError,
  onDelete,
  onRefresh,
}: SidebarProps) {
  return (
    <aside
      id="lecture-library"
      aria-label="Lecture library"
      className={`fixed inset-y-0 left-0 z-40 flex w-[min(19rem,calc(100vw-2.5rem))] flex-col border-r border-line-soft bg-panel/95 backdrop-blur-xl transition-transform duration-300 lg:w-80 lg:translate-x-0 lg:bg-panel/70 ${
        isOpen ? "visible translate-x-0" : "invisible -translate-x-full lg:visible"
      }`}
    >
      <div className="flex items-start justify-between px-4 pb-4 pt-5">
        <div className="flex items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-lg border border-brass-400/30 bg-gradient-to-b from-brass-400/20 to-transparent text-brass-300">
            <BookOpen size={17} strokeWidth={1.8} aria-hidden="true" />
          </span>
          <div>
            <p className="font-display text-lg leading-none tracking-tight text-ink">
              LecturaRAG
            </p>
            <p className="mt-1 text-[10px] uppercase tracking-[0.18em] text-faint">
              Study workspace
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close library"
          className="inline-flex size-8 items-center justify-center rounded-md text-faint hover:bg-white/5 hover:text-ink lg:hidden"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="scrollbar-slim flex-1 overflow-y-auto px-4 pb-6">
        <UploadZone
          uploading={uploading}
          serverError={uploadError}
          onUpload={onUpload}
          onClearServerError={onClearUploadError}
        />
        <DocumentList
          documents={documents}
          selectedId={selectedId}
          isLoading={isLoading}
          error={error}
          deletingId={deletingId}
          onSelect={onSelect}
          onDelete={onDelete}
          onRetry={onRefresh}
        />
      </div>

      <div className="border-t border-line-soft px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-[10px] text-muted">
            <span
              className={`size-1.5 rounded-full ${
                isOnline ? "bg-jade shadow-[0_0_6px_rgba(94,234,212,0.7)]" : "bg-rose"
              }`}
              aria-hidden="true"
            />
            {isOnline ? "API connected" : "API offline"}
          </span>
          <span className="rounded-full border border-line px-2 py-0.5 text-[9px] font-medium uppercase tracking-wider text-faint">
            {health?.llm_mode === "openai-compatible" ? "LLM engine" : "Local engine"}
          </span>
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-faint">
          Every answer is grounded in your pages.
        </p>
      </div>
    </aside>
  );
}
