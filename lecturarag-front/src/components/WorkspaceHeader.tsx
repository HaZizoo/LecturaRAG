import {
  ChevronRight,
  Layers3,
  Menu,
  MessageSquareText,
  Timer,
} from "lucide-react";
import type { KeyboardEvent } from "react";
import type { DocumentSummary, TabId } from "../lib/types";

const TABS = [
  { id: "chat", label: "Chat", icon: MessageSquareText },
  { id: "flashcards", label: "Flashcards", icon: Layers3 },
  { id: "quiz", label: "Quiz", icon: Timer },
] as const satisfies readonly { id: TabId; label: string; icon: typeof Timer }[];

interface WorkspaceHeaderProps {
  document: DocumentSummary | null;
  activeTab: TabId;
  isSidebarOpen: boolean;
  onTabChange: (tab: TabId) => void;
  onOpenSidebar: () => void;
}

export function WorkspaceHeader({
  document,
  activeTab,
  isSidebarOpen,
  onTabChange,
  onOpenSidebar,
}: WorkspaceHeaderProps) {
  const handleTabKey = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const currentIndex = TABS.findIndex((tab) => tab.id === activeTab);
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (currentIndex + direction + TABS.length) % TABS.length;
    const nextTab = TABS[nextIndex].id;
    onTabChange(nextTab);
    window.document.getElementById(`tab-${nextTab}`)?.focus();
  };
  return (
    <header className="border-b border-line-soft bg-canvas/55 backdrop-blur">
      <div className="flex items-center justify-between border-b border-line-soft px-4 py-3 lg:hidden">
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Open lecture library"
          aria-expanded={isSidebarOpen}
          aria-controls="lecture-library"
          className="inline-flex size-8 items-center justify-center rounded-md border border-line bg-panel text-muted"
        >
          <Menu size={16} aria-hidden="true" />
        </button>
        <span className="font-display text-base text-ink">LecturaRAG</span>
        <span className="text-[10px] uppercase tracking-[0.16em] text-faint">Workspace</span>
      </div>

      <div className="px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] text-faint">
              <span>Workspace</span>
              <ChevronRight size={10} aria-hidden="true" />
              <span className="text-muted">
                {document ? "Active lecture" : "No lecture selected"}
              </span>
            </div>
            <h1 className="mt-2 truncate font-display text-2xl leading-tight text-ink sm:text-[28px]">
              {document?.title ?? "Your study workspace"}
            </h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-faint">
              {document ? (
                <>
                  <span className="rounded border border-line bg-panel-raised px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-brass-300">
                    {document.file_type === "pdf" ? "PDF" : "Markdown"}
                  </span>
                  <span>
                    <strong className="font-semibold text-muted">{document.page_count}</strong>{" "}
                    pages
                  </span>
                  <span aria-hidden="true" className="size-0.5 rounded-full bg-line" />
                  <span>
                    <strong className="font-semibold text-muted">{document.chunk_count}</strong>{" "}
                    indexed chunks
                  </span>
                  <span aria-hidden="true" className="size-0.5 rounded-full bg-line" />
                  <span className="truncate">{document.filename}</span>
                </>
              ) : (
                <span>Upload a lecture to start studying with citations.</span>
              )}
            </div>
          </div>

          {document ? (
            <nav
              aria-label="Study tools"
              className="flex w-full overflow-x-auto rounded-xl border border-line-soft bg-panel/70 p-1 xl:w-auto"
              role="tablist"
              onKeyDown={handleTabKey}
            >
              {TABS.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    aria-controls={`panel-${tab.id}`}
                    id={`tab-${tab.id}`}
                    onClick={() => onTabChange(tab.id)}
                    className={`inline-flex flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-medium transition-colors xl:flex-none ${
                      isActive
                        ? "bg-[#1a2533] text-brass-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
                        : "text-faint hover:bg-white/[0.03] hover:text-muted"
                    }`}
                  >
                    <Icon
                      size={14}
                      className={isActive ? "text-brass-300" : ""}
                      aria-hidden="true"
                    />
                    {tab.label}
                  </button>
                );
              })}
            </nav>
          ) : null}
        </div>
      </div>
    </header>
  );
}
