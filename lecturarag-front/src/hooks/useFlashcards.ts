import { useCallback, useEffect, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { CardStatus, Deck } from "../lib/types";

export function useFlashcards(documentId: string | null) {
  const [deck, setDeck] = useState<Deck | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!documentId) {
      setDeck(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getDecks(documentId);
      setDeck(payload.decks[0] ?? null);
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
    async (count = 12): Promise<boolean> => {
      if (!documentId) return false;
      setIsGenerating(true);
      setError(null);
      try {
        const created = await api.generateDeck(documentId, count);
        setDeck(created);
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

  const setCardStatus = useCallback(
    async (cardId: string, status: CardStatus): Promise<boolean> => {
      const previousStatus = deck?.cards.find((card) => card.id === cardId)?.status ?? "new";
      setStatusError(null);
      setDeck((current) =>
        current
          ? {
              ...current,
              cards: current.cards.map((card) =>
                card.id === cardId ? { ...card, status } : card,
              ),
            }
          : current,
      );

      try {
        await api.updateCardStatus(cardId, status);
        return true;
      } catch (err) {
        setDeck((current) =>
          current
            ? {
                ...current,
                cards: current.cards.map((card) =>
                  card.id === cardId ? { ...card, status: previousStatus } : card,
                ),
              }
            : current,
        );
        setStatusError(getErrorMessage(err));
        return false;
      }
    },
    [deck],
  );

  return {
    deck,
    isLoading,
    isGenerating,
    error,
    statusError,
    generate,
    setCardStatus,
    reload: load,
    clearStatusError: () => setStatusError(null),
  };
}
