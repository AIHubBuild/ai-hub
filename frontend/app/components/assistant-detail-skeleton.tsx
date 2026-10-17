export function AssistantDetailSkeleton() {
  return (
    <div aria-hidden="true" className="max-w-3xl animate-pulse">
      <div className="border-b border-line pb-8">
        <div className="h-3 w-24 rounded bg-line" />
        <div className="mt-4 flex items-center justify-between">
          <div className="h-10 w-1/2 rounded bg-line" />
          <div className="h-6 w-24 rounded-full bg-line" />
        </div>
        <div className="mt-5 space-y-2">
          <div className="h-4 w-full rounded bg-line/70" />
          <div className="h-4 w-5/6 rounded bg-line/70" />
        </div>
      </div>
      <div className="mt-8 h-3 w-28 rounded bg-line" />
      <div className="mt-3 flex gap-1.5">
        <div className="h-7 w-28 rounded-md bg-surface-muted" />
        <div className="h-7 w-32 rounded-md bg-surface-muted" />
        <div className="h-7 w-24 rounded-md bg-surface-muted" />
      </div>
      <div className="mt-8 h-36 rounded-2xl bg-surface-muted" />
    </div>
  );
}
