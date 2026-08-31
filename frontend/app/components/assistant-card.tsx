import type { AssistantCatalogueEntry } from "../lib/catalogue";

const STATUS_STYLES: Record<AssistantCatalogueEntry["status"], {
  badge: string;
  label: string;
}> = {
  available: {
    badge:
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
    label: "Ready for integration",
  },
  in_development: {
    badge: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    label: "In development",
  },
};

export function AssistantCard({
  assistant,
}: {
  assistant: AssistantCatalogueEntry;
}) {
  const status = STATUS_STYLES[assistant.status];
  const deployed = assistant.launch_url !== null;

  return (
    <article className="flex flex-col rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          {assistant.name}
        </h3>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${status.badge}`}
        >
          {status.label}
        </span>
      </div>
      <p className="mb-4 flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        {assistant.description}
      </p>
      {assistant.capabilities.length > 0 && (
        <ul
          className="mb-5 flex flex-wrap gap-1.5"
          aria-label={`${assistant.name} capabilities`}
        >
          {assistant.capabilities.map((capability) => (
            <li
              key={capability}
              className="rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            >
              {capability}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-zinc-100 pt-4 dark:border-zinc-800">
        {deployed ? (
          <a
            href={assistant.launch_url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Launch ${assistant.name} (opens in a new tab)`}
            className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
          >
            Launch
            <ExternalLinkIcon />
          </a>
        ) : (
          <span className="text-sm text-zinc-500 dark:text-zinc-400">
            Not yet integrated
          </span>
        )}
        <a
          href={assistant.repository_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${assistant.name} repository (opens in a new tab)`}
          className="inline-flex items-center gap-1 text-sm text-zinc-500 underline-offset-2 hover:text-zinc-800 hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          Repository
          <ExternalLinkIcon />
        </a>
      </div>
    </article>
  );
}

export function ExternalLinkIcon() {
  return (
    <svg
      className="ml-1 h-3.5 w-3.5"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
    >
      <path d="M6.5 3H3v10h10V9.5M9.5 3H13v3.5M13 3 7 9" />
    </svg>
  );
}
