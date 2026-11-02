"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface HoldingSelectionContextValue {
  selectedSymbol: string | null;
  select: (symbol: string) => void;
  clear: () => void;
}

const HoldingSelectionContext = createContext<HoldingSelectionContextValue | null>(null);

export function HoldingSelectionProvider({ children }: { children: React.ReactNode }) {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

  const select = useCallback((symbol: string) => {
    setSelectedSymbol((current) => (current === symbol ? null : symbol));
  }, []);

  const clear = useCallback(() => setSelectedSymbol(null), []);

  const value = useMemo(() => ({ selectedSymbol, select, clear }), [selectedSymbol, select, clear]);

  return <HoldingSelectionContext.Provider value={value}>{children}</HoldingSelectionContext.Provider>;
}

export function useHoldingSelection(): HoldingSelectionContextValue {
  const ctx = useContext(HoldingSelectionContext);
  if (!ctx) throw new Error("useHoldingSelection must be used within HoldingSelectionProvider");
  return ctx;
}
