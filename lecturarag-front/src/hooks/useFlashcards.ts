import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";
import type { CardStatus, Deck } from "../lib/types";

interface DeckState {
  documentId: string | null;
  deck: Deck | null;
}

export function useFlashcards(documentId: string | null) {
  // Keep the deck keyed by document so Lecture A's cards can never be shown
  // under Lecture B's header, even for the render before the load effect runs.
  const [deckState, setDeckState] = useState<DeckState>({ documentId: null, deck: null });
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const requestToken = useRef(0);
  const activeDocument = useRef(documentId);
  // Keep the latest selection available to async callbacks that resolve after
  // the user has already moved to another lecture.
  activeDocument.current = documentId;

  const deck = deckState.documentId === documentId ? deckState.deck : null;

  const load = useCallback(async () => {
    const token = ++requestToken.current;
    if (!documentId) {
      setDeckState({ documentId: null, deck: null });
      setIsLoading(false);
      setError(null);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getDecks(documentId);
      if (token !== requestToken.current) return;
      setDeckState({ documentId, deck: payload.decks[0] ?? null });
    } catch (err) {
      if (token !== requestToken.current) return;
      setDeckState({ documentId, deck: null });
      setError(getErrorMessage(err));
    } finally {
      if (token === requestToken.current) setIsLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setStatusError(null);
  }, [documentId]);

  const generate = useCallback(
    async (count = 12): Promise<boolean> => {
      if (!documentId) return false;
      setIsGenerating(true);
      setError(null);
      try {
        const created = await api.generateDeck(documentId, count);
        // Drop stale results instead of overwriting the newly-selected deck.
        if (activeDocument.current !== documentId) return false;
        setDeckState({ documentId, deck: created });
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

  const setCardStatus = useCallback(
    async (cardId: string, status: CardStatus): Promise<boolean> => {
      const targetDocument = documentId;
      const targetDeck = deckState.deck;
      const previousStatus =
        targetDeck?.cards.find((card) => card.id === cardId)?.status ?? "new";
      const applyStatus = (nextStatus: CardStatus) => {
        setDeckState((current) => {
          if (
            !current.deck ||
            current.documentId !== targetDocument ||
            current.deck.id !== targetDeck?.id
          ) {
            return current;
          }
          return {
            ...current,
            deck: {
              ...current.deck,
              cards: current.deck.cards.map((card) =>
                card.id === cardId ? { ...card, status: nextStatus } : card,
              ),
            },
          };
        });
      };

      setStatusError(null);
      applyStatus(status);

      try {
        await api.updateCardStatus(cardId, status);
        return true;
      } catch (err) {
        if (activeDocument.current === targetDocument) {
          applyStatus(previousStatus);
          setStatusError(getErrorMessage(err));
        }
        return false;
      }
    },
    [deckState.deck, documentId],
  );

  return {
    deck,
    // While a newly-selected document is loading, do not briefly show an empty
    // state with the previous document's metadata.
    isLoading: isLoading || (documentId !== null && deckState.documentId !== documentId),
    isGenerating,
    error,
    statusError,
    generate,
    setCardStatus,
    reload: load,
    clearStatusError: () => setStatusError(null),
  };
}
