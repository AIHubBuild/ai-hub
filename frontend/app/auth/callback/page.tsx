import { Suspense } from "react";
import { AuthCallbackView } from "./callback-view";

export default function AuthCallbackPage() {
  return (
    <main className="mx-auto w-full max-w-xl flex-1 px-4 py-12 sm:px-6">
      <Suspense fallback={<p className="text-sm text-muted">Verifying…</p>}>
        <AuthCallbackView />
      </Suspense>
    </main>
  );
}
