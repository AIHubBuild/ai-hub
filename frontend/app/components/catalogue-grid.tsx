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
        message="The backend API is unreachable. Start the FastAPI server on port 8000, then reload the page."
      />
    );
  }

  if (catalogue.length === 0) {
    return (
      <p className="rounded-xl border border-zinc-200 bg-zinc-50 p-8 text-center text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
        No assistants have been registered yet.
      </p>
    );
  }

  return (
    <ul className="grid list-none gap-4 md:grid-cols-2 lg:grid-cols-3">
      {catalogue.map((assistant) => (
        <li key={assistant.id} className="flex">
          <AssistantCard assistant={assistant} />
        </li>
      ))}
    </ul>
  );
}
