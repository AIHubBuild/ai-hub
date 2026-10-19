import { UserActivity } from "./user-activity";

export default async function AdminUserActivityPage({
  params,
}: {
  params: Promise<{ userId: string }>;
}) {
  const { userId } = await params;
  return <UserActivity userId={userId} />;
}
