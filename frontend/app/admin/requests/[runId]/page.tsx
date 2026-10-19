import { RequestDetail } from "./request-detail";

export default async function AdminRequestDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <RequestDetail runId={runId} />;
}
