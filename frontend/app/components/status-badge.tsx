import type { AssistantStatus } from "../lib/catalogue";

const STATUS_STYLES: Record<
  AssistantStatus,
  { badge: string; label: string; dot: string }
> = {
  available: {
    badge: "border-success/25 text-success",
    label: "Available",
    dot: "bg-success",
  },
  in_development: {
    badge: "border-line text-muted",
    label: "In development",
    dot: "bg-muted",
  },
};

export function StatusBadge({ status }: { status: AssistantStatus }) {
  const styles = STATUS_STYLES[status];
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border bg-transparent px-2.5 py-1 text-[11px] font-medium ${styles.badge}`}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${styles.dot}`}
      />
      {styles.label}
    </span>
  );
}
