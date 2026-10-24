import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { Quiz } from "../lib/types";

interface QuizState {
  documentId: string | null;
  quiz: Quiz | null;
}

export function useQuiz(documentId: string | null) {
  const [quizState, setQuizState] = useState<QuizState>({ documentId: null, quiz: null });
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestToken = useRef(0);
  const activeDocument = useRef(documentId);
  activeDocument.current = documentId;

  const quiz = quizState.documentId === documentId ? quizState.quiz : null;

  const load = useCallback(async () => {
    const token = ++requestToken.current;
    if (!documentId) {
      setQuizState({ documentId: null, quiz: null });
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getQuizzes(documentId);
      if (token !== requestToken.current) return;
      setQuizState({ documentId, quiz: payload.quizzes[0] ?? null });
    } catch (err) {
      if (token !== requestToken.current) return;
      setQuizState({ documentId, quiz: null });
      setError(getErrorMessage(err));
    } finally {
      if (token === requestToken.current) setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = useCallback(
    async (numQuestions = 6): Promise<boolean> => {
      if (!documentId) return false;
      setIsGenerating(true);
      setError(null);
      try {
        const created = await api.generateQuiz(documentId, numQuestions);
        // A switch mid-generation must not overwrite the new lecture's quiz.
        if (activeDocument.current !== documentId) return false;
        setQuizState({ documentId, quiz: created });
        return true;
      } catch (err) {
        if (activeDocument.current === documentId) setError(getErrorMessage(err));
        return false;
      } finally {
        setIsGenerating(false);
      }
    },
    [documentId],
  );

  return {
    quiz,
    isLoading: isLoading || (documentId !== null && quizState.documentId !== documentId),
    isGenerating,
    error,
    generate,
    reload: load,
  };
}
