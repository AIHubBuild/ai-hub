export function CapabilityTags({
  capabilities,
  label,
}: {
  capabilities: string[];
  label?: string;
}) {
  if (capabilities.length === 0) {
    return null;
  }
  return (
    <ul
      className="flex flex-wrap gap-1.5"
      aria-label={label ?? "Capabilities"}
    >
      {capabilities.map((capability) => (
        <li
          key={capability}
          className="rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
        >
          {capability}
        </li>
      ))}
    </ul>
  );
}
