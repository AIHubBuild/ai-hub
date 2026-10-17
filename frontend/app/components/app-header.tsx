import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeftIcon } from "./icons";

export function AppHeader({
  title,
  eyebrow,
  description,
  icon,
}: {
  title: string;
  eyebrow: string;
  description: string;
  icon: ReactNode;
}) {
  return (
    <header className="mb-8 border-b border-line pb-8 sm:mb-10 sm:pb-10">
      <nav aria-label="Breadcrumb" className="mb-7">
        <Link
          href="/"
          className="inline-flex items-center text-sm font-medium text-muted transition-colors hover:text-ink focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
        >
          <ArrowLeftIcon />
          Workspace
        </Link>
      </nav>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-line bg-surface text-ink">
              {icon}
            </span>
            <p className="ui-eyebrow">{eyebrow}</p>
          </div>
          <h1 className="ui-display mt-4 text-4xl text-ink sm:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted sm:text-base">
            {description}
          </p>
        </div>
        <p className="hidden max-w-56 text-right text-xs leading-5 text-muted lg:block">
          Private to your account. Nothing here is shared with other users.
        </p>
      </div>
    </header>
  );
}
