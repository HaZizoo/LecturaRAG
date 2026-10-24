import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertCircle, BookMarked, Loader2, RefreshCw } from "lucide-react";

export const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-brass-400 px-4 py-2.5 text-sm font-semibold text-[#211509] transition-colors hover:bg-brass-300 disabled:cursor-not-allowed disabled:opacity-50";

export const secondaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-panel-raised px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-brass-400/40 hover:bg-[#16212e] disabled:cursor-not-allowed disabled:opacity-50";

export const ghostButton =
  "inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm text-muted transition-colors hover:bg-white/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40";

export const iconButton =
  "inline-flex size-8 items-center justify-center rounded-md text-faint transition-colors hover:bg-white/5 hover:text-ink disabled:opacity-40";

export function Spinner({ className = "size-4" }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden="true" />;
}

export function PageStamp({ page, className = "" }: { page: number; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-line bg-panel-raised px-2 py-0.5 text-[10px] font-semibold tracking-wide text-muted ${className}`}
    >
      <BookMarked size={11} aria-hidden="true" />
      <span className="sr-only">Source </span>Page {page}
    </span>
  );
}

export function ErrorNotice({
  message,
  onRetry,
  compact = false,
}: {
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      role="alert"
      className={`flex items-start gap-2 rounded-lg border border-rose/20 bg-rose/[0.06] text-rose ${
        compact ? "px-3 py-2 text-[11px]" : "px-4 py-3 text-xs"
      }`}
    >
      <AlertCircle size={compact ? 14 : 16} className="mt-0.5 shrink-0" aria-hidden="true" />
      <p className="min-w-0 flex-1 leading-relaxed">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1 rounded border border-rose/25 px-2 py-1 text-[10px] font-semibold transition-colors hover:bg-rose/10"
        >
          <RefreshCw size={11} aria-hidden="true" />
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyPanel({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto flex size-14 items-center justify-center rounded-panel border border-brass-400/20 bg-brass-400/[0.06] text-brass-300">
          <Icon size={24} aria-hidden="true" />
        </div>
        <h2 className="mt-5 font-display text-2xl text-ink">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
        {children ? <div className="mt-6 flex justify-center">{children}</div> : null}
      </div>
    </div>
  );
}

export function SkeletonBlock({ className = "h-24" }: { className?: string }) {
  return <div className={`skeleton rounded-panel ${className}`} aria-hidden="true" />;
}
