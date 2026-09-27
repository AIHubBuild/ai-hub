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
      className="rounded-xl border border-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h3 className="text-base font-medium text-zinc-900 dark:text-zinc-50">
        {title}
      </h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        {message}
      </p>
      <ReloadButton />
    </div>
  );
}
