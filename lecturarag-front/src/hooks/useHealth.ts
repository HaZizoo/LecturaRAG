import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Health } from "../lib/types";

export function useHealth(): { health: Health | null; isOnline: boolean } {
  const [health, setHealth] = useState<Health | null>(null);
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .getHealth()
      .then((payload) => {
        if (active) {
          setHealth(payload);
          setIsOnline(true);
        }
      })
      .catch(() => {
        if (active) setIsOnline(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { health, isOnline };
}
