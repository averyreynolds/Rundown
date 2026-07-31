"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { AdvisorFilingRef } from "@/lib/rundown-api";

interface AdvisorContextValue {
  isOpen: boolean;
  scopeSymbol: string | null;
  scopeFilingRef: AdvisorFilingRef | null;
  open: (scopeSymbol?: string, scopeFilingRef?: AdvisorFilingRef) => void;
  close: () => void;
}

const AdvisorContext = createContext<AdvisorContextValue | null>(null);

export function AdvisorProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [scopeSymbol, setScopeSymbol] = useState<string | null>(null);
  const [scopeFilingRef, setScopeFilingRef] = useState<AdvisorFilingRef | null>(null);

  const open = useCallback((symbol?: string, filingRef?: AdvisorFilingRef) => {
    setScopeSymbol(symbol ?? null);
    setScopeFilingRef(filingRef ?? null);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => setIsOpen(false), []);

  const value = useMemo(
    () => ({ isOpen, scopeSymbol, scopeFilingRef, open, close }),
    [isOpen, scopeSymbol, scopeFilingRef, open, close],
  );

  return <AdvisorContext.Provider value={value}>{children}</AdvisorContext.Provider>;
}

export function useAdvisor(): AdvisorContextValue {
  const ctx = useContext(AdvisorContext);
  if (!ctx) throw new Error("useAdvisor must be used within AdvisorProvider");
  return ctx;
}
