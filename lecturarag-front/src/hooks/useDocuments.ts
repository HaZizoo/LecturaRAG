import { useCallback, useEffect, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { DocumentSummary } from "../lib/types";

const STORAGE_KEY = "lecturarag:document-id";

function persistSelection(documentId: string | null) {
  if (documentId) window.localStorage.setItem(STORAGE_KEY, documentId);
  else window.localStorage.removeItem(STORAGE_KEY);
}

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    window.localStorage.getItem(STORAGE_KEY),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const selectDocument = useCallback((documentId: string | null) => {
    setSelectedId(documentId);
    persistSelection(documentId);
  }, []);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.listDocuments();
      setDocuments(payload.documents);
      setSelectedId((current) => {
        const next =
          current && payload.documents.some((document) => document.id === current)
            ? current
            : (payload.documents[0]?.id ?? null);
        persistSelection(next);
        return next;
      });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const upload = useCallback(
    async (file: File): Promise<boolean> => {
      setUploading(true);
      setUploadError(null);
      try {
        const payload = await api.uploadDocument(file);
        setDocuments((current) => [
          payload.document,
          ...current.filter((document) => document.id !== payload.document.id),
        ]);
        selectDocument(payload.document.id);
        return true;
      } catch (err) {
        setUploadError(getErrorMessage(err));
        return false;
      } finally {
        setUploading(false);
      }
    },
    [selectDocument],
  );

  const remove = useCallback(
    async (documentId: string): Promise<boolean> => {
      setDeletingId(documentId);
      setError(null);
      try {
        await api.deleteDocument(documentId);
        const remaining = documents.filter((document) => document.id !== documentId);
        setDocuments(remaining);
        if (selectedId === documentId) {
          selectDocument(remaining[0]?.id ?? null);
        }
        return true;
      } catch (err) {
        setError(getErrorMessage(err));
        return false;
      } finally {
        setDeletingId(null);
      }
    },
    [documents, selectedId, selectDocument],
  );

  const selectedDocument =
    documents.find((document) => document.id === selectedId) ?? null;

  return {
    documents,
    selectedDocument,
    selectDocument,
    isLoading,
    error,
    uploading,
    uploadError,
    deletingId,
    upload,
    remove,
    refresh,
    clearUploadError: () => setUploadError(null),
  };
}
