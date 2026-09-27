import Link from "next/link";

export default function AssistantNotFound() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <div className="max-w-md rounded-xl border border-zinc-200 bg-zinc-50 p-8 dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          Assistant not found
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          There is no assistant registered with this identifier. It may have
          been renamed or removed.
        </p>
        <Link
          href="/"
          className="mt-5 inline-flex items-center justify-center rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
        >
          Back to dashboard
        </Link>
      </div>
    </main>
  );
}
