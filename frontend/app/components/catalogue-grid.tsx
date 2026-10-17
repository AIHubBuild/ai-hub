import { fetchCatalogue } from "../lib/catalogue";
import { AssistantCard } from "./assistant-card";
import { ErrorPanel } from "./error-panel";

export async function CatalogueGrid() {
  let catalogue;
  try {
    catalogue = await fetchCatalogue();
  } catch {
    return (
      <ErrorPanel
        title="Could not load the assistant catalogue"
        message="The assistant catalogue is temporarily unavailable. Please try again in a moment."
      />
    );
  }

  if (catalogue.length === 0) {
    return (
      <p className="rounded-[28px] border border-dashed border-line bg-surface/60 p-10 text-center text-sm text-muted">
        No assistants have been registered yet.
      </p>
    );
  }

  return (
    <ul className="grid list-none gap-4 md:grid-cols-2">
      {catalogue.map((assistant, index) => (
        <li key={assistant.id} className="flex">
          <AssistantCard assistant={assistant} index={index} />
        </li>
      ))}
    </ul>
  );
}
