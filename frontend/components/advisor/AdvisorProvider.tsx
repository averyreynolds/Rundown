"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface AdvisorContextValue {
  isOpen: boolean;
  scopeSymbol: string | null;
  open: (scopeSymbol?: string) => void;
  close: () => void;
}

const AdvisorContext = createContext<AdvisorContextValue | null>(null);

export function AdvisorProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [scopeSymbol, setScopeSymbol] = useState<string | null>(null);

  const open = useCallback((symbol?: string) => {
    setScopeSymbol(symbol ?? null);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => setIsOpen(false), []);

  const value = useMemo(() => ({ isOpen, scopeSymbol, open, close }), [isOpen, scopeSymbol, open, close]);

  return <AdvisorContext.Provider value={value}>{children}</AdvisorContext.Provider>;
}

export function useAdvisor(): AdvisorContextValue {
  const ctx = useContext(AdvisorContext);
  if (!ctx) throw new Error("useAdvisor must be used within AdvisorProvider");
  return ctx;
}
