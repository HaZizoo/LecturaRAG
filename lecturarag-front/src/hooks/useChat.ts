import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { ChatEntry } from "../lib/types";

export function useChat(documentId: string | null) {
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const activeDocument = useRef<string | null>(documentId);
  const sendingRef = useRef(false);

  useEffect(() => {
    activeDocument.current = documentId;
  }, [documentId]);

  useEffect(() => {
    let active = true;
    if (!documentId) {
      setMessages([]);
      setIsLoadingHistory(false);
      return;
    }

    setIsLoadingHistory(true);
    setError(null);
    setMessages([]);

    api
      .getChatHistory(documentId)
      .then((payload) => {
        if (active) setMessages(payload.messages);
      })
      .catch((err: unknown) => {
        if (active) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (active) setIsLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [documentId, historyVersion]);

  const reloadHistory = useCallback(() => {
    setHistoryVersion((version) => version + 1);
  }, []);

  const send = useCallback(
    async (raw: string): Promise<boolean> => {
      const content = raw.trim();
      if (!content || !documentId || sendingRef.current) return false;

      sendingRef.current = true;
      setIsSending(true);
      setError(null);

      const optimistic: ChatEntry = {
        id: `local-${Date.now()}`,
        role: "user",
        content,
        citations: [],
        model: "input",
        fallback_used: false,
        created_at: new Date().toISOString(),
      };
      setMessages((current) => [...current, optimistic]);

      try {
        const response = await api.sendChat(documentId, content);
        if (activeDocument.current !== documentId) return true;

        const assistant: ChatEntry = {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          sources: response.sources,
          model: response.model,
          fallback_used: response.fallback_used,
          created_at: response.created_at,
        };
        setMessages((current) => [...current, assistant]);
        return true;
      } catch (err) {
        setMessages((current) => current.filter((message) => message.id !== optimistic.id));
        setError(getErrorMessage(err));
        return false;
      } finally {
        sendingRef.current = false;
        setIsSending(false);
      }
    },
    [documentId],
  );

  return {
    messages,
    isLoadingHistory,
    isSending,
    error,
    send,
    reloadHistory,
    clearError: () => setError(null),
  };
}
