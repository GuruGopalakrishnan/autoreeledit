"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar({ projectId }: { projectId?: string }) {
  const pathname = usePathname();
  const inEditor = pathname?.startsWith("/editor/") ?? false;

  const items: { label: string; href: string | null; active: boolean }[] = [
    { label: "Project Setup", href: "/", active: pathname === "/" },
    { label: "Edit", href: projectId ? `/editor/${projectId}` : null, active: inEditor },
    { label: "Text Animations", href: inEditor ? "#section-style" : null, active: false },
    { label: "Subject Mask", href: inEditor ? "#section-mask" : null, active: false },
    { label: "Export", href: inEditor ? "#section-export" : null, active: false },
  ];

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-white/10 bg-[#0e0e14] p-4">
      <div className="mb-6 px-2 text-lg font-bold tracking-tight">
        AUTO<span className="text-[#7c5cfc]">REEL</span>
      </div>
      <nav className="space-y-1">
        {items.map((item) =>
          item.href ? (
            <Link
              key={item.label}
              href={item.href}
              className={`block rounded-lg px-3 py-2 text-sm ${
                item.active ? "bg-[#7c5cfc]/15 text-[#a993ff] font-medium" : "text-neutral-300 hover:bg-white/5"
              }`}
            >
              {item.label}
            </Link>
          ) : (
            <div
              key={item.label}
              className="cursor-not-allowed rounded-lg px-3 py-2 text-sm text-neutral-600"
              title="Open a project first"
            >
              {item.label}
            </div>
          )
        )}
      </nav>
    </aside>
  );
}
