import type { Metadata } from "next";
import { AuthShell } from "../../components/auth/auth-shell";
import { CompleteRegistrationView } from "./complete-registration";

export const metadata: Metadata = {
  title: "Complete registration",
  description: "Finish setting up your AI Hub Assist profile.",
};

export default function CompleteRegistrationPage() {
  return (
    <AuthShell width="wide">
      <CompleteRegistrationView />
    </AuthShell>
  );
}
