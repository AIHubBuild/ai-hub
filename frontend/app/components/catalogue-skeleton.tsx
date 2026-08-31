export function CatalogueSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"
    >
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          className="animate-pulse rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="mb-4 flex items-center justify-between">
            <div className="h-5 w-2/5 rounded bg-zinc-200 dark:bg-zinc-800" />
            <div className="h-5 w-20 rounded-full bg-zinc-200 dark:bg-zinc-800" />
          </div>
          <div className="mb-4 space-y-2">
            <div className="h-3 w-full rounded bg-zinc-100 dark:bg-zinc-800" />
            <div className="h-3 w-full rounded bg-zinc-100 dark:bg-zinc-800" />
            <div className="h-3 w-3/4 rounded bg-zinc-100 dark:bg-zinc-800" />
          </div>
          <div className="mb-6 flex gap-1.5">
            <div className="h-6 w-24 rounded-md bg-zinc-100 dark:bg-zinc-800" />
            <div className="h-6 w-28 rounded-md bg-zinc-100 dark:bg-zinc-800" />
            <div className="h-6 w-20 rounded-md bg-zinc-100 dark:bg-zinc-800" />
          </div>
          <div className="border-t border-zinc-100 pt-4 dark:border-zinc-800">
            <div className="h-8 w-2/5 rounded-lg bg-zinc-100 dark:bg-zinc-800" />
          </div>
        </div>
      ))}
    </div>
  );
}
