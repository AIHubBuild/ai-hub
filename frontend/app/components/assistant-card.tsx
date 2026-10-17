import Link from "next/link";
import type { ReactElement } from "react";
import type { AssistantCatalogueEntry } from "../lib/catalogue";
import {
  ArrowRightIcon,
  ChatSupportIcon,
  DocumentTextIcon,
  ExternalLinkIcon,
} from "./icons";

const ASSISTANT_ICONS: Record<
  string,
  (props: { className?: string }) => ReactElement
> = {
  "resume-ats": DocumentTextIcon,
  "it-support-copilot": ChatSupportIcon,
};

const ASSISTANT_COPY: Record<
  string,
  { summary: string; action: string; capabilities: string[] }
> = {
  "resume-ats": {
    summary:
      "Match your resume to a real job description, see what is missing, and export a tailored resume and cover letter.",
    action: "Open Resume ATS",
    capabilities: [
      "Evidence-based match score",
      "Keyword gaps",
      "Tailored resume",
      "Cover letter and DOCX export",
    ],
  },
  "it-support-copilot": {
    summary:
      "Work through an IT issue with a support engineer, grounded in the knowledge base, with a ticket that tracks the outcome.",
    action: "Open IT Support",
    capabilities: [
      "Issue classification",
      "Low-risk troubleshooting",
      "Knowledge-base guidance",
      "Ticket and escalation tracking",
    ],
  },
};

export function AssistantCard({
  assistant,
  index,
}: {
  assistant: AssistantCatalogueEntry;
  index: number;
}) {
  const integrated = assistant.app_path !== null;
  const deployed = assistant.launch_url !== null;
  const Icon = ASSISTANT_ICONS[assistant.id] ?? DocumentTextIcon;
  const copy = ASSISTANT_COPY[assistant.id];
  const isSupport = assistant.id === "it-support-copilot";
  const actionLabel = copy?.action ?? "Open assistant";
  const capabilities = copy?.capabilities ?? assistant.capabilities;

  return (
    <article
      className={`group relative flex h-full flex-col overflow-hidden rounded-[28px] p-6 ring-1 ring-line/80 transition duration-200 hover:-translate-y-0.5 hover:ring-ink/20 sm:p-8 ${
        isSupport ? "bg-surface-muted" : "bg-surface"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <span
          className={`flex h-11 w-11 items-center justify-center rounded-2xl ${
            isSupport ? "bg-ink text-canvas" : "bg-accent-soft text-accent"
          }`}
        >
          <Icon className="h-5 w-5" />
        </span>
        <span className="font-mono text-[11px] tracking-[0.16em] text-muted">
          {String(index + 1).padStart(2, "0")}
        </span>
      </div>

      <h3 className="ui-display mt-7 text-3xl text-ink sm:text-[2rem]">
        {assistant.name}
      </h3>
      <p className="mt-3 max-w-md text-sm leading-6 text-muted">
        {copy?.summary ?? assistant.description}
      </p>

      <ul className="mt-7 grid gap-x-6 gap-y-2.5 text-sm text-ink-soft sm:grid-cols-2">
        {capabilities.map((capability) => (
          <li key={capability} className="flex items-start gap-2.5">
            <span
              aria-hidden="true"
              className={`mt-[0.55rem] h-1 w-1 shrink-0 rounded-full ${
                isSupport ? "bg-ink/50" : "bg-accent"
              }`}
            />
            <span>{capability}</span>
          </li>
        ))}
      </ul>

      <div className="mt-auto flex flex-wrap items-center gap-x-5 gap-y-3 pt-9">
        {integrated ? (
          <Link
            href={assistant.app_path ?? "/"}
            className="ui-button ui-button-primary"
          >
            {actionLabel}
            <ArrowRightIcon />
          </Link>
        ) : deployed ? (
          <a
            href={assistant.launch_url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Launch ${assistant.name} (opens in a new tab)`}
            className="ui-button ui-button-primary"
          >
            Launch
            <ExternalLinkIcon />
          </a>
        ) : (
          <span className="ui-button ui-button-secondary cursor-default text-muted">
            In development
          </span>
        )}

        <Link
          href={`/assistants/${assistant.id}`}
          className="inline-flex items-center text-sm font-medium text-ink-soft underline-offset-4 transition-colors hover:text-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          aria-label={`View ${assistant.name} details`}
        >
          Details
        </Link>
      </div>
    </article>
  );
}
