import Link from "next/link";

export default function AssistantNotFound() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
      <div className="max-w-md rounded-2xl bg-surface p-8 ring-1 ring-line/80">
        <p className="ui-eyebrow">Not found</p>
        <h1 className="ui-display mt-3 text-3xl text-ink">
          Assistant not found
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          There is no assistant registered with this identifier. It may have
          been renamed or removed.
        </p>
        <Link href="/" className="ui-button ui-button-primary mt-6">
          Back to workspace
        </Link>
      </div>
    </main>
  );
}
