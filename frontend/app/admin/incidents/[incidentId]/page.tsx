import { IncidentDetail } from "./incident-detail";

export default async function AdminIncidentDetailPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}) {
  const { incidentId } = await params;
  return <IncidentDetail incidentId={incidentId} />;
}
