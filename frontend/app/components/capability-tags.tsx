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
          className="rounded-md border border-line bg-transparent px-2.5 py-1 text-xs text-ink-soft"
        >
          {capability}
        </li>
      ))}
    </ul>
  );
}
