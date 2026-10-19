import { Suspense } from "react";
import { AuthShell } from "../../components/auth/auth-shell";
import { Spinner } from "../../components/auth/spinner";
import { AuthCallbackView } from "./callback-view";

export default function AuthCallbackPage() {
  return (
    <AuthShell>
      <Suspense
        fallback={
          <div className="flex items-center justify-center py-10 text-sm text-muted">
            <Spinner className="mr-2" />
            Verifying…
          </div>
        }
      >
        <AuthCallbackView />
      </Suspense>
    </AuthShell>
  );
}
