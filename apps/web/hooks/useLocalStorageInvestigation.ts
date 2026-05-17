"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { readJson, storageKey, writeJson } from "@/lib/localStorage";
import { throttle } from "@/lib/throttle";
import type { InvestigationState } from "@/hooks/useInvestigation";

const THROTTLE_MS = 500;

export function useLocalStorageInvestigation(id: string | undefined) {
  const key = id ? storageKey("investigation", id) : null;
  const [hydrated, setHydrated] = useState<InvestigationState | null>(null);
  const hydratedRef = useRef(false);

  // Read once, on mount, so the SSE hook can seed itself.
  useEffect(() => {
    if (!key || hydratedRef.current) return;
    hydratedRef.current = true;
    setHydrated(readJson<InvestigationState>(key));
  }, [key]);

  const save = useMemo(() => {
    if (!key) return null;
    return throttle((state: InvestigationState) => writeJson(key, state), THROTTLE_MS);
  }, [key]);

  useEffect(() => {
    return () => {
      save?.flush();
    };
  }, [save]);

  return { hydrated, save } as const;
}
