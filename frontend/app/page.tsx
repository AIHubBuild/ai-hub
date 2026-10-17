import { Suspense } from "react";
import { CatalogueGrid } from "./components/catalogue-grid";
import { CatalogueSkeleton } from "./components/catalogue-skeleton";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-10 sm:px-6 sm:pt-14 lg:px-8">
      <section
        aria-labelledby="dashboard-heading"
        className="grid gap-8 border-b border-line pb-10 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.55fr)] lg:items-end"
      >
        <div>
          <p className="ui-eyebrow">AI productivity workspace</p>
          <h1
            id="dashboard-heading"
            className="ui-display mt-4 max-w-3xl text-[2.75rem] text-ink sm:text-6xl"
          >
            Two focused tools. One place to get work done.
          </h1>
        </div>
        <div className="lg:pb-1">
          <p className="text-sm leading-6 text-muted sm:text-base">
            Prepare your resume for a specific role, or work through an IT
            issue with a support engineer. Both tools keep a private record
            of your work.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3 text-xs font-medium text-muted">
            <span className="inline-flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-success"
              />
              2 tools available
            </span>
            <span aria-hidden="true" className="h-3 w-px bg-line" />
            <span>Private workspace</span>
          </div>
        </div>
      </section>

      <section
        id="tools"
        aria-labelledby="tools-heading"
        className="scroll-mt-24 pt-9 sm:pt-10"
      >
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h2
              id="tools-heading"
              className="ui-display text-2xl text-ink sm:text-3xl"
            >
              Your tools
            </h2>
            <p className="mt-1 text-sm text-muted">
              Start where the work is.
            </p>
          </div>
          <p className="hidden text-xs font-medium text-muted sm:block">
            Select a tool to begin
          </p>
        </div>
        <Suspense fallback={<CatalogueSkeleton />}>
          <CatalogueGrid />
        </Suspense>
      </section>
    </main>
  );
}
