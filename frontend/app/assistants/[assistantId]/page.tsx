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
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-7">
        <Link
          href="/"
          className="inline-flex items-center text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          <ArrowLeftIcon />
          Workspace
        </Link>
      </nav>

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
        message="This assistant is temporarily unavailable. Please try again in a moment."
      />
    );
  }

  if (assistant === null) {
    notFound();
  }

  return (
    <article className="max-w-3xl">
      <header className="border-b border-line pb-8">
        <p className="ui-eyebrow">Tool details</p>
        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <h1 className="ui-display text-4xl text-ink sm:text-5xl">
            {assistant.name}
          </h1>
          <StatusBadge status={assistant.status} />
        </div>
        <p className="mt-4 text-sm leading-6 text-muted sm:text-base">
          {assistant.description}
        </p>
      </header>

      <section aria-labelledby="capabilities-heading" className="mt-8">
        <h2
          id="capabilities-heading"
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted"
        >
          Capabilities
        </h2>
        <div className="mt-3">
          <CapabilityTags
            capabilities={assistant.capabilities}
            label={`${assistant.name} capabilities`}
          />
        </div>
      </section>

      <section
        aria-labelledby="launch-heading"
        className="mt-8 rounded-2xl bg-surface-muted/60 p-6"
      >
        <h2
          id="launch-heading"
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted"
        >
          Launch
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink-soft">
          {assistant.app_path !== null
            ? "This assistant is integrated with AI Hub and runs inside your private workspace."
            : assistant.launch_url !== null
              ? "This assistant has a hosted deployment."
              : "This assistant is not yet integrated with AI Hub. The launch flow arrives in a later phase. You can review its source in the repository below."}
        </p>
        {assistant.app_path !== null && (
          <Link
            href={assistant.app_path}
            className="ui-button ui-button-primary mt-4"
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
            className="ui-button ui-button-primary mt-4"
          >
            Launch
            <ExternalLinkIcon />
          </a>
        )}
      </section>

      <section aria-labelledby="reference-heading" className="mt-8">
        <h2
          id="reference-heading"
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted"
        >
          Reference
        </h2>
        <a
          href={assistant.repository_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${assistant.name} repository (opens in a new tab)`}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-ink-soft underline-offset-4 transition-colors hover:text-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          View repository
          <ExternalLinkIcon />
        </a>
      </section>
    </article>
  );
}
