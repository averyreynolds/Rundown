"use client";

import { useAdvisor } from "./AdvisorProvider";

export function AdvisorTrigger() {
  const { open } = useAdvisor();

  return (
    <button
      onClick={() => open()}
      aria-label="Ask about your portfolio"
      className="fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-ink text-white shadow-lg shadow-ink/10 transition-transform hover:-translate-y-0.5 sm:bottom-8 sm:right-8 sm:h-auto sm:w-auto sm:gap-2 sm:px-4 sm:py-3"
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path
          d="M2 4.5A1.5 1.5 0 0 1 3.5 3h9A1.5 1.5 0 0 1 14 4.5v5A1.5 1.5 0 0 1 12.5 11H8l-3 2.5V11H3.5A1.5 1.5 0 0 1 2 9.5v-5Z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
      </svg>
      <span className="hidden text-sm font-medium sm:inline">Ask about your portfolio</span>
    </button>
  );
}
