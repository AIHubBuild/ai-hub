import Link from "next/link";
import { Suspense } from "react";
import { CatalogueGrid } from "./components/catalogue-grid";
import { CatalogueSkeleton } from "./components/catalogue-skeleton";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#assistants"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-zinc-900 focus:px-4 focus:py-2 focus:text-sm focus:text-white dark:focus:bg-zinc-50 dark:focus:text-zinc-900"
      >
        Skip to assistants
      </a>

      <header className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
        <nav
          aria-label="Main"
          className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-6"
        >
          <Link
            href="/"
            className="text-sm font-semibold tracking-tight text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-900 dark:text-zinc-50 dark:focus-visible:outline-zinc-50"
          >
            AI Hub
          </Link>
          <ul className="flex items-center gap-6 text-sm">
            <li>
              <a
                href="#assistants"
                className="text-zinc-600 transition-colors hover:text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
              >
                Assistants
              </a>
            </li>
            <li>
              <Link
                href="/"
                aria-current="page"
                className="text-zinc-900 dark:text-zinc-50"
              >
                Dashboard
              </Link>
            </li>
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
        <section
          aria-labelledby="dashboard-heading"
          className="mb-10 max-w-2xl"
        >
          <h1
            id="dashboard-heading"
            className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
          >
            AI Hub
          </h1>
          <p className="mt-3 text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
            A platform where AI assistants work together. Explore the
            assistants available on the platform — integration and launch
            wiring arrive in a later phase.
          </p>
        </section>

        <section
          id="assistants"
          aria-labelledby="assistants-heading"
          className="scroll-mt-20"
        >
          <div className="mb-5 flex items-baseline justify-between gap-4">
            <h2
              id="assistants-heading"
              className="text-lg font-medium text-zinc-900 dark:text-zinc-50"
            >
              Assistants
            </h2>
            <ul className="flex items-center gap-4 text-xs text-zinc-500 dark:text-zinc-400">
              <li className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Ready for integration
              </li>
              <li className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                In development
              </li>
            </ul>
          </div>
          <Suspense fallback={<CatalogueSkeleton />}>
            <CatalogueGrid />
          </Suspense>
        </section>
      </main>

      <footer className="border-t border-zinc-200 dark:border-zinc-800">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-6 py-8 text-sm text-zinc-500 sm:flex-row sm:items-center sm:justify-between dark:text-zinc-400">
          <p>AI Hub — a platform where AI assistants work together.</p>
          <p>Backend integration, launch, and authentication: later phase.</p>
        </div>
      </footer>
    </div>
  );
}
