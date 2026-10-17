import { AppHeader } from "../../components/app-header";
import { ChatSupportIcon } from "../../components/icons";
import { SupportWorkspace } from "./support-workspace";

export default function SupportAppPage() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-12 lg:px-8">
      <AppHeader
        eyebrow="IT Support Copilot"
        title="AI IT Support Copilot"
        description="Describe your IT issue. The Copilot classifies it, retrieves knowledge-base guidance, troubleshoots with you, and tracks a support ticket through resolution or escalation."
        icon={<ChatSupportIcon className="h-4 w-4" />}
      />
      <SupportWorkspace />
    </main>
  );
}
