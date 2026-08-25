export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 px-6 dark:bg-zinc-950">
      <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        AI Hub
      </h1>
      <p className="max-w-md text-center text-zinc-600 dark:text-zinc-400">
        A platform where AI assistants work together. Foundation scaffold
        running — assistants will be added as modules in later phases.
      </p>
      <p className="text-sm text-zinc-500 dark:text-zinc-500">
        Backend health check:{" "}
        <a
          href="http://localhost:8000/health"
          className="underline underline-offset-2 hover:text-zinc-800 dark:hover:text-zinc-300"
        >
          http://localhost:8000/health
        </a>
      </p>
    </main>
  );
}
