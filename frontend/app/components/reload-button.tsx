"use client";

import { useRouter } from "next/navigation";

export function ReloadButton() {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.refresh()}
      className="ui-button ui-button-secondary mt-5"
    >
      Reload
    </button>
  );
}
