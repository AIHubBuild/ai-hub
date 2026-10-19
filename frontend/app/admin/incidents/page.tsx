import { IncidentsView } from "./incidents-view";

export default async function AdminIncidentsPage({
  searchParams,
}: {
  searchParams: Promise<{
    linked_run_id?: string | string[];
    linked_user_id?: string | string[];
  }>;
}) {
  const params = await searchParams;
  const linkedRunId =
    typeof params.linked_run_id === "string" ? params.linked_run_id : "";
  const linkedUserId =
    typeof params.linked_user_id === "string" ? params.linked_user_id : "";

  return (
    <IncidentsView
      initialLinkedRunId={linkedRunId}
      initialLinkedUserId={linkedUserId}
    />
  );
}
