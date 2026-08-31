import { fetchCatalogue } from "../lib/catalogue";
import { AssistantCard } from "./assistant-card";
import { ReloadButton } from "./reload-button";

export async function CatalogueGrid() {
  let catalogue;
  try {
    catalogue = await fetchCatalogue();
  } catch {
    return (
      <div
        role="alert"
        className="rounded-xl border border-zinc-200 bg-zinc-50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900"
      >
        <h3 className="text-base font-medium text-zinc-900 dark:text-zinc-50">
          Could not load the assistant catalogue
        </h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
          The backend API is unreachable. Start the FastAPI server on port
          8000, then reload the page.
        </p>
        <ReloadButton />
      </div>
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
