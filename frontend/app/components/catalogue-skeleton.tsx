export function CatalogueSkeleton() {
  return (
    <div aria-hidden="true" className="grid gap-4 md:grid-cols-2">
      {[0, 1].map((index) => (
        <div
          key={index}
          className={`animate-pulse rounded-[28px] p-6 ring-1 ring-line/70 sm:p-8 ${
            index === 1 ? "bg-surface-muted" : "bg-surface"
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="h-11 w-11 rounded-2xl bg-line" />
            <div className="h-3 w-6 rounded bg-line" />
          </div>
          <div className="mt-7 h-9 w-2/3 rounded bg-line" />
          <div className="mt-4 space-y-2">
            <div className="h-3 w-full rounded bg-line/70" />
            <div className="h-3 w-4/5 rounded bg-line/70" />
          </div>
          <div className="mt-7 grid gap-2 sm:grid-cols-2">
            <div className="h-3 w-4/5 rounded bg-line/60" />
            <div className="h-3 w-3/5 rounded bg-line/60" />
            <div className="h-3 w-2/3 rounded bg-line/60" />
            <div className="h-3 w-1/2 rounded bg-line/60" />
          </div>
          <div className="mt-9 h-10 w-40 rounded-xl bg-line" />
        </div>
      ))}
    </div>
  );
}
