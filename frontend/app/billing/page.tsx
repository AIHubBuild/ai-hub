import { Suspense } from "react";
import { BillingView } from "./billing-view";

export const metadata = {
  title: "Billing",
};

export default function BillingPage() {
  return (
    <Suspense fallback={null}>
      <BillingView />
    </Suspense>
  );
}
