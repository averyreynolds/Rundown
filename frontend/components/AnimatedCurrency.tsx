"use client";

import { useEffect, useRef, useState } from "react";
import { formatCurrency } from "@/lib/format";

function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

/**
 * Counts up from 0 to `value` once on mount -- the page's one authored
 * motion moment (see DESIGN.md "Motion"). Respects reduced-motion by
 * rendering the final value immediately instead of animating.
 */
export function AnimatedCurrency({ value, className }: { value: number; className?: string }) {
  const [display, setDisplay] = useState(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? value : 0
  );
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reduceMotion ? 0 : 900;
    let raf: number;

    function tick(ts: number) {
      if (startRef.current === null) startRef.current = ts;
      const progress = duration === 0 ? 1 : Math.min((ts - startRef.current) / duration, 1);
      setDisplay(value * easeOutExpo(progress));
      if (progress < 1) raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <span className={className}>{formatCurrency(display)}</span>;
}
