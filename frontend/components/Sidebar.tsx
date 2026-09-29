const NAV_ITEMS = [
  { label: "Project Setup", active: true },
  { label: "Edit", active: false },
  { label: "Text Animations", active: false },
  { label: "Subject Mask", active: false },
  { label: "Export", active: false },
];

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-white/10 bg-[#0e0e14] p-4">
      <div className="mb-6 px-2 text-lg font-bold tracking-tight">
        AUTO<span className="text-[#7c5cfc]">REEL</span>
      </div>
      <nav className="space-y-1">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.label}
            className={`rounded-lg px-3 py-2 text-sm ${
              item.active
                ? "bg-[#7c5cfc]/15 text-[#a993ff] font-medium"
                : "text-neutral-500 cursor-not-allowed"
            }`}
            title={item.active ? undefined : "Coming in a later phase"}
          >
            {item.label}
          </div>
        ))}
      </nav>
    </aside>
  );
}
