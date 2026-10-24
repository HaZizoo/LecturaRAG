import { useRef, useState } from "react";
import { FileUp, Loader2, UploadCloud } from "lucide-react";
import { ErrorNotice } from "./ui";

const MAX_BYTES = 20 * 1024 * 1024;
const ACCEPTED = [".pdf", ".md", ".markdown"];

interface UploadZoneProps {
  uploading: boolean;
  serverError: string | null;
  onUpload: (file: File) => Promise<boolean>;
  onClearServerError: () => void;
}

export function UploadZone({
  uploading,
  serverError,
  onUpload,
  onClearServerError,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file || uploading) return;
    setLocalError(null);
    onClearServerError();

    const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
    if (!ACCEPTED.includes(extension)) {
      setLocalError("Only PDF and Markdown (.md, .markdown) lectures are supported.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setLocalError("That file is larger than the 20 MB upload limit.");
      return;
    }
    await onUpload(file);
  };

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={(event) => {
          if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
          setDragActive(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDragActive(false);
          void handleFile(event.dataTransfer.files[0]);
        }}
        className={`rounded-panel border border-dashed transition-colors ${
          dragActive
            ? "border-brass-400/70 bg-brass-400/[0.08]"
            : "border-line bg-white/[0.015] hover:border-brass-400/35 hover:bg-white/[0.03]"
        }`}
      >
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="flex w-full flex-col items-center gap-2 rounded-panel px-4 py-6 text-center disabled:opacity-60"
        >
          <span className="flex size-9 items-center justify-center rounded-lg border border-line bg-panel-raised text-brass-300">
            {uploading ? (
              <Loader2 size={17} className="animate-spin" aria-hidden="true" />
            ) : (
              <UploadCloud size={17} aria-hidden="true" />
            )}
          </span>
          <span className="text-[13px] font-medium text-ink">
            {uploading ? "Parsing and indexing…" : "Drop a lecture or browse"}
          </span>
          <span className="text-[11px] leading-relaxed text-faint">
            PDF, MD · up to 20 MB
          </span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(",")}
          className="hidden"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void handleFile(file);
          }}
        />
      </div>

      {localError ? (
        <div className="mt-2">
          <ErrorNotice message={localError} compact />
        </div>
      ) : null}
      {serverError ? (
        <div className="mt-2">
          <ErrorNotice message={serverError} compact />
        </div>
      ) : null}

      <p className="mt-2 flex items-center gap-1.5 text-[10px] text-faint">
        <FileUp size={11} aria-hidden="true" />
        Text is indexed locally with exact page numbers.
      </p>
    </div>
  );
}
