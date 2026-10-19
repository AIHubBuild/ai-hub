import type { Metadata } from "next";
import { CompleteRegistrationView } from "./complete-registration";

export const metadata: Metadata = {
  title: "Complete registration",
  description: "Finish setting up your AI Hub profile.",
};

export default function CompleteRegistrationPage() {
  return <CompleteRegistrationView />;
}
