"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", match: (pathname: string) => pathname === "/" },
  {
    href: "/#assistants",
    label: "Assistants",
    match: (pathname: string) => pathname.startsWith("/assistants"),
  },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
      <nav
        aria-label="Main"
        className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-6"
      >
        <Link
          href="/"
          className="text-sm font-semibold tracking-tight text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-900 dark:text-zinc-50 dark:focus-visible:outline-zinc-50"
        >
          AI Hub
        </Link>
        <ul className="flex items-center gap-6 text-sm">
          {NAV_LINKS.map((link) => {
            const active = link.match(pathname);
            return (
              <li key={link.label}>
                <Link
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    active
                      ? "font-medium text-zinc-900 dark:text-zinc-50"
                      : "text-zinc-600 transition-colors hover:text-zinc-900 focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:text-zinc-50"
                  }
                >
                  {link.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </header>
  );
}
