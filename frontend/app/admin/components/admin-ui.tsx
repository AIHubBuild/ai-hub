"use client";

import type { ReactNode } from "react";
import type { AdminWindow, RequestStatus } from "../../lib/admin";

export function formatDateTime(value: string | null): string {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatLatency(value: number | null): string {
  if (value === null) {
    return "Unknown";
  }
  return `${Math.round(value)} ms`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function AdminPageHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <header className="border-b border-line pb-7">
      <p className="ui-eyebrow">{eyebrow}</p>
      <h1 className="ui-display mt-3 text-3xl text-ink sm:text-4xl">
        {title}
      </h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
        {description}
      </p>
    </header>
  );
}

export function WindowPicker({
  value,
  onChange,
}: {
  value: AdminWindow;
  onChange: (value: AdminWindow) => void;
}) {
  const options: Array<{ value: AdminWindow; label: string }> = [
    { value: "24h", label: "24 hours" },
    { value: "7d", label: "7 days" },
    { value: "30d", label: "30 days" },
  ];
  return (
    <div className="inline-flex rounded-lg bg-surface-muted p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
            value === option.value
              ? "bg-surface text-ink shadow-sm"
              : "text-muted hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="rounded-2xl bg-surface p-5 ring-1 ring-line/80">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">
        {label}
      </p>
      <p className="ui-display mt-3 text-3xl text-ink">{value}</p>
      {detail ? <p className="mt-2 text-xs text-muted">{detail}</p> : null}
    </div>
  );
}

export function StatusPill({ status }: { status: RequestStatus }) {
  const styles =
    status === "success"
      ? "border-success/25 text-success"
      : "border-danger/25 text-danger";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${styles}`}
    >
      {status === "success" ? "Success" : "Failed"}
    </span>
  );
}

export function EmptyState({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface/60 p-10 text-center">
      <h2 className="ui-display text-2xl text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
        {message}
      </p>
    </div>
  );
}

export function AdminErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80"
    >
      <p className="ui-eyebrow text-danger">Error</p>
      <h2 className="ui-display mt-3 text-2xl text-ink">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
        {message}
      </p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="ui-button ui-button-secondary mt-5"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}

export function LoadingPanel({ label }: { label: string }) {
  return (
    <div
      role="status"
      className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80"
    >
      <span className="mx-auto block h-2 w-24 animate-pulse rounded-full bg-surface-muted" />
      <p className="mt-4 text-sm text-muted">{label}</p>
    </div>
  );
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) {
    return null;
  }
  return (
    <div className="mt-5 flex items-center justify-between gap-3">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="ui-button ui-button-secondary"
      >
        Previous
      </button>
      <p className="text-xs font-medium text-muted">
        Page {page} of {totalPages}
      </p>
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="ui-button ui-button-secondary"
      >
        Next
      </button>
    </div>
  );
}

export function Panel({
  title,
  description,
  children,
  action,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="rounded-2xl bg-surface p-5 ring-1 ring-line/80 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {description ? (
            <p className="mt-1 text-xs leading-5 text-muted">{description}</p>
          ) : null}
        </div>
        {action}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
