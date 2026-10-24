import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { ChatEntry } from "../lib/types";

interface ConversationState {
  documentId: string | null;
  messages: ChatEntry[];
}

export function useChat(documentId: string | null) {
  // Key the transcript by document; messages from Lecture A are never rendered
  // under Lecture B, not even for the render before the load effect runs.
  const [conversation, setConversation] = useState<ConversationState>({
    documentId: null,
    messages: [],
  });
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyVersion, setHistoryVersion] = useState(0);
  const activeDocument = useRef<string | null>(documentId);
  activeDocument.current = documentId;
  const sendingRef = useRef(false);
  const messages =
    conversation.documentId === documentId ? conversation.messages : [];
  const hasLoadedConversation = conversation.documentId === documentId;

  useEffect(() => {
    let active = true;
    if (!documentId) {
      setConversation({ documentId: null, messages: [] });
      setIsLoadingHistory(false);
      setError(null);
      return;
    }

    setIsLoadingHistory(true);
    setError(null);
    setConversation({ documentId, messages: [] });

    api
      .getChatHistory(documentId)
      .then((payload) => {
        if (!active) return;
        setConversation((current) => {
          if (current.documentId !== documentId) return current;
          const known = new Set(payload.messages.map((message) => message.id));
          const pending = current.messages.filter((message) => !known.has(message.id));
          return { documentId, messages: [...payload.messages, ...pending] };
        });
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
      setConversation((current) => {
        const base =
          current.documentId === documentId
            ? current
            : { documentId, messages: [] as ChatEntry[] };
        return { ...base, messages: [...base.messages, optimistic] };
      });

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
        setConversation((current) => {
          if (current.documentId !== documentId) return current;
          return { ...current, messages: [...current.messages, assistant] };
        });
        return true;
      } catch (err) {
        if (activeDocument.current === documentId) {
          setConversation((current) => {
            if (current.documentId !== documentId) return current;
            return {
              ...current,
              messages: current.messages.filter((message) => message.id !== optimistic.id),
            };
          });
          setError(getErrorMessage(err));
        }
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
    isLoadingHistory:
      isLoadingHistory || (documentId !== null && !hasLoadedConversation),
    isSending,
    error,
    send,
    reloadHistory,
    clearError: () => setError(null),
  };
}
