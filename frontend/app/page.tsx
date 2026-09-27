import { Suspense } from "react";
import { CatalogueGrid } from "./components/catalogue-grid";
import { CatalogueSkeleton } from "./components/catalogue-skeleton";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <section aria-labelledby="dashboard-heading" className="mb-10 max-w-2xl">
        <h1
          id="dashboard-heading"
          className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          AI Hub
        </h1>
        <p className="mt-3 text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          A platform where AI assistants work together. Explore the assistants
          available on the platform — integration and launch wiring arrive in a
          later phase.
        </p>
      </section>

      <section
        id="assistants"
        aria-labelledby="assistants-heading"
        className="scroll-mt-20"
      >
        <div className="mb-5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
          <h2
            id="assistants-heading"
            className="text-lg font-medium text-zinc-900 dark:text-zinc-50"
          >
            Assistants
          </h2>
          <ul className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
            <li className="flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2 w-2 rounded-full bg-emerald-500" />
              Ready for integration
            </li>
            <li className="flex items-center gap-1.5">
              <span aria-hidden="true" className="h-2 w-2 rounded-full bg-amber-500" />
              In development
            </li>
          </ul>
        </div>
        <Suspense fallback={<CatalogueSkeleton />}>
          <CatalogueGrid />
        </Suspense>
      </section>
    </main>
  );
}
