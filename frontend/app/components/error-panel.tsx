import { ReloadButton } from "./reload-button";

export function ErrorPanel({
  title = "Something went wrong",
  message,
}: {
  title?: string;
  message: string;
}) {
  return (
    <div
      role="alert"
      className="rounded-2xl bg-surface p-8 text-center ring-1 ring-line/80 sm:p-10"
    >
      <p className="ui-eyebrow text-danger">Error</p>
      <h3 className="ui-display mt-3 text-2xl text-ink">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted">
        {message}
      </p>
      <ReloadButton />
    </div>
  );
}
