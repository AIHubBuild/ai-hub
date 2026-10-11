import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AssistantDetailSkeleton } from "../../components/assistant-detail-skeleton";
import { CapabilityTags } from "../../components/capability-tags";
import { ErrorPanel } from "../../components/error-panel";
import { ArrowLeftIcon, ExternalLinkIcon } from "../../components/icons";
import { StatusBadge } from "../../components/status-badge";
import { fetchAssistantById } from "../../lib/catalogue";

export default async function AssistantDetailPage(
  props: PageProps<"/assistants/[assistantId]">,
) {
  const { assistantId } = await props.params;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <Link
        href="/#assistants"
        className="mb-8 inline-flex items-center text-sm text-zinc-500 transition-colors hover:text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
      >
        <ArrowLeftIcon />
        All assistants
      </Link>

      <Suspense fallback={<AssistantDetailSkeleton />}>
        <AssistantDetailContent assistantId={assistantId} />
      </Suspense>
    </main>
  );
}

async function AssistantDetailContent({
  assistantId,
}: {
  assistantId: string;
}) {
  let assistant;
  try {
    assistant = await fetchAssistantById(assistantId);
  } catch {
    return (
      <ErrorPanel
        title="Could not load this assistant"
        message="The backend API is unreachable. Start the FastAPI server on port 8000, then reload the page."
      />
    );
  }

  if (assistant === null) {
    notFound();
  }

  return (
    <article className="max-w-2xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          {assistant.name}
        </h1>
        <StatusBadge status={assistant.status} />
      </div>

      <p className="text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
        {assistant.description}
      </p>

      <section aria-labelledby="capabilities-heading" className="mt-8">
        <h2
          id="capabilities-heading"
          className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
        >
          Capabilities
        </h2>
        <CapabilityTags
          capabilities={assistant.capabilities}
          label={`${assistant.name} capabilities`}
        />
      </section>

      <section
        aria-labelledby="launch-heading"
        className="mt-8 rounded-xl border border-zinc-200 bg-zinc-50 p-6 dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h2
          id="launch-heading"
          className="text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
        >
          Launch
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          {assistant.app_path !== null
            ? "This assistant is integrated with AI Hub."
            : assistant.launch_url !== null
              ? "This assistant has a hosted deployment."
              : "This assistant is not yet integrated with AI Hub. The launch flow arrives in a later phase — you can review its source in the repository below."}
        </p>
        {assistant.app_path !== null && (
          <Link
            href={assistant.app_path}
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
          >
            Open in AI Hub
          </Link>
        )}
        {assistant.app_path === null && assistant.launch_url !== null && (
          <a
            href={assistant.launch_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Launch ${assistant.name} (opens in a new tab)`}
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200 dark:focus-visible:outline-zinc-50"
          >
            Launch
            <ExternalLinkIcon />
          </a>
        )}
      </section>

      <section aria-labelledby="reference-heading" className="mt-8">
        <h2
          id="reference-heading"
          className="mb-3 text-sm font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
        >
          Reference
        </h2>
        <a
          href={assistant.repository_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${assistant.name} repository (opens in a new tab)`}
          className="inline-flex items-center gap-1 text-sm text-zinc-600 underline-offset-2 hover:text-zinc-900 hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
        >
          View repository
          <ExternalLinkIcon />
        </a>
      </section>
    </article>
  );
}
