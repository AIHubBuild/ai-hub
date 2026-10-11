import Link from "next/link";
import type { AssistantCatalogueEntry } from "../lib/catalogue";
import { CapabilityTags } from "./capability-tags";
import { ExternalLinkIcon } from "./icons";
import { StatusBadge } from "./status-badge";

export function AssistantCard({
  assistant,
}: {
  assistant: AssistantCatalogueEntry;
}) {
  const integrated = assistant.app_path !== null;
  const deployed = assistant.launch_url !== null;

  return (
    <article className="flex flex-col rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-50">
          {assistant.name}
        </h3>
        <StatusBadge status={assistant.status} />
      </div>
      <p className="mb-4 flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        {assistant.description}
      </p>
      <div className="mb-5">
        <CapabilityTags
          capabilities={assistant.capabilities}
          label={`${assistant.name} capabilities`}
        />
      </div>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-zinc-100 pt-4 dark:border-zinc-800">
        {integrated ? (
          <Link
            href={assistant.app_path ?? "/"}
            className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
          >
            Open
          </Link>
        ) : deployed ? (
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
        <span className="flex items-center gap-3">
          <Link
            href={`/assistants/${assistant.id}`}
            aria-label={`View ${assistant.name} details`}
            className="inline-flex items-center text-sm font-medium text-zinc-700 underline-offset-2 hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-200"
          >
            Details
          </Link>
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
        </span>
      </div>
    </article>
  );
}
