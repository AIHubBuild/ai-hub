import type { Metadata } from "next";
import { ProfileView } from "./profile-view";

export const metadata: Metadata = {
  title: "Profile",
  description: "Manage your AI Hub account profile.",
};

export default function ProfilePage() {
  return <ProfileView />;
}
