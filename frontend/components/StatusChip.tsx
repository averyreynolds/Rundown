type StatusChipTone = "stale" | "error" | "flag";

const TONE_CLASSES: Record<StatusChipTone, string> = {
  stale: "bg-status-stale-soft text-status-stale",
  error: "bg-status-error-soft text-status-error",
  flag: "bg-accent-soft text-accent-ink",
};

export function StatusChip({
  tone,
  children,
}: {
  tone: StatusChipTone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium leading-none ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}
