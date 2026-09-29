"use client";

import type { Caption } from "@/lib/api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function Timeline({
  captions,
  duration,
  currentTime,
  selectedId,
  onSeek,
  onSelect,
}: {
  captions: Caption[];
  duration: number;
  currentTime: number;
  selectedId: number | null;
  onSeek: (time: number) => void;
  onSelect: (id: number) => void;
}) {
  const safeDuration = Math.max(duration, 0.1);
  const playheadPct = Math.min(100, (currentTime / safeDuration) * 100);

  return (
    <div>
      <div className="mb-1 flex justify-between text-[10px] text-neutral-500">
        <span>0:00</span>
        <span>{formatTime(duration)}</span>
      </div>
      <div
        className="relative h-16 cursor-pointer rounded-lg bg-black/30"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const ratio = (e.clientX - rect.left) / rect.width;
          onSeek(Math.max(0, Math.min(safeDuration, ratio * safeDuration)));
        }}
      >
        {captions.map((c) => {
          const left = (c.start / safeDuration) * 100;
          const width = Math.max(0.5, ((c.end - c.start) / safeDuration) * 100);
          const selected = c.id === selectedId;
          return (
            <button
              key={c.id}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(c.id);
                onSeek(c.start);
              }}
              title={c.text}
              style={{ left: `${left}%`, width: `${width}%` }}
              className={`absolute top-1 bottom-1 overflow-hidden rounded border px-1.5 text-left text-[10px] leading-tight transition-colors ${
                selected
                  ? "border-white bg-[#7c5cfc] text-white"
                  : c.isKeyword
                    ? "border-red-500/40 bg-red-500/20 text-red-200 hover:bg-red-500/30"
                    : "border-white/15 bg-white/10 text-neutral-300 hover:bg-white/15"
              }`}
            >
              <span className="line-clamp-2">{c.text}</span>
            </button>
          );
        })}

        <div
          className="pointer-events-none absolute top-0 bottom-0 w-0.5 bg-white"
          style={{ left: `${playheadPct}%` }}
        />
      </div>
    </div>
  );
}
