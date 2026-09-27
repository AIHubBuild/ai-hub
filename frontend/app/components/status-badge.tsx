import type { AssistantStatus } from "../lib/catalogue";

const STATUS_STYLES: Record<AssistantStatus, {
  badge: string;
  label: string;
  dot: string;
}> = {
  available: {
    badge:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
    label: "Ready for integration",
    dot: "bg-emerald-500",
  },
  in_development: {
    badge: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    label: "In development",
    dot: "bg-amber-500",
  },
};

export function StatusBadge({ status }: { status: AssistantStatus }) {
  const styles = STATUS_STYLES[status];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${styles.badge}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${styles.dot}`}
      />
      {styles.label}
    </span>
  );
}
