export function AssistantDetailSkeleton() {
  return (
    <div aria-hidden="true" className="max-w-2xl animate-pulse">
      <div className="mb-8 h-4 w-24 rounded bg-zinc-200 dark:bg-zinc-800" />
      <div className="mb-4 flex items-center justify-between">
        <div className="h-7 w-1/2 rounded bg-zinc-200 dark:bg-zinc-800" />
        <div className="h-6 w-32 rounded-full bg-zinc-200 dark:bg-zinc-800" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-zinc-100 dark:bg-zinc-800" />
        <div className="h-4 w-5/6 rounded bg-zinc-100 dark:bg-zinc-800" />
      </div>
      <div className="mt-8 h-3 w-28 rounded bg-zinc-200 dark:bg-zinc-800" />
      <div className="mt-3 flex gap-1.5">
        <div className="h-6 w-28 rounded-md bg-zinc-100 dark:bg-zinc-800" />
        <div className="h-6 w-32 rounded-md bg-zinc-100 dark:bg-zinc-800" />
        <div className="h-6 w-24 rounded-md bg-zinc-100 dark:bg-zinc-800" />
      </div>
      <div className="mt-8 h-32 rounded-xl bg-zinc-100 dark:bg-zinc-800" />
    </div>
  );
}
