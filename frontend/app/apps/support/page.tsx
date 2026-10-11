import Link from "next/link";
import { ArrowLeftIcon } from "../../components/icons";
import { SupportWorkspace } from "./support-workspace";

export default function SupportAppPage() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
      <Link
        href="/#assistants"
        className="mb-8 inline-flex items-center text-sm text-zinc-500 transition-colors hover:text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
      >
        <ArrowLeftIcon />
        All assistants
      </Link>

      <section aria-labelledby="support-heading" className="mb-10 max-w-2xl">
        <h1
          id="support-heading"
          className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50"
        >
          AI IT Support Copilot
        </h1>
        <p className="mt-3 text-base leading-relaxed text-zinc-600 dark:text-zinc-400">
          Describe your IT issue. The Copilot classifies it, retrieves
          knowledge-base guidance, troubleshoots with you, and tracks a
          support ticket through resolution or escalation.
        </p>
      </section>

      <SupportWorkspace />
    </main>
  );
}
