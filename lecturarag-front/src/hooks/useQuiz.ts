import { useCallback, useEffect, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { Quiz } from "../lib/types";

export function useQuiz(documentId: string | null) {
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!documentId) {
      setQuiz(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getQuizzes(documentId);
      setQuiz(payload.quizzes[0] ?? null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
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
        setQuiz(created);
        return true;
      } catch (err) {
        setError(getErrorMessage(err));
        return false;
      } finally {
        setIsGenerating(false);
      }
    },
    [documentId],
  );

  return {
    quiz,
    isLoading,
    isGenerating,
    error,
    generate,
    reload: load,
  };
}
