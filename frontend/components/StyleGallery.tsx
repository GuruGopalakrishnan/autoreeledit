"use client";

import { fontFamilyForPath } from "@/lib/fonts";
import type { StylePreset } from "@/lib/api";

const SAMPLE_TEXT = "Create Better Content";

const NAME_OVERRIDES: Record<string, string> = {
  "typewriter-glow": "Typewriter Glow",
  "corporate-lower-third": "Corporate Lower Third",
  "name-tag": "Name Tag",
  "decrypt-reveal": "Decrypt Reveal",
  "glitch-pop": "Glitch Pop",
  "wave-bounce": "Wave Bounce",
  "rise-up": "Rise Up",
  "blur-pop": "Blur Pop",
};

function PreviewCard({ preset, selected, onSelect }: { preset: StylePreset; selected: boolean; onSelect: () => void }) {
  const fontFamily = fontFamilyForPath(preset.font);
  const textShadow = preset.outline_color
    ? [-1, 1].flatMap((dx) => [-1, 1].map((dy) => `${dx * preset.outline_width * 0.6}px ${dy * preset.outline_width * 0.6}px 0 ${preset.outline_color}`)).join(", ")
    : undefined;

  return (
    <button
      onClick={onSelect}
      className={`overflow-hidden rounded-xl border text-left transition-colors ${
        selected ? "border-[#7c5cfc] ring-2 ring-[#7c5cfc]/40" : "border-white/10 hover:border-white/25"
      }`}
    >
      <div className="relative flex aspect-[9/16] items-end justify-center overflow-hidden bg-[#f0f0f0] p-3">
        <span
          className={`animate-preview-${preset.animation} inline-block rounded px-2 py-1 text-center text-[15px] font-bold leading-tight`}
          style={{
            fontFamily,
            color: preset.color,
            backgroundColor: preset.bg_color ?? undefined,
            textShadow,
          }}
        >
          {SAMPLE_TEXT}
        </span>
      </div>
      <div className="bg-[#111117] px-2.5 py-2">
        <p className="truncate text-xs font-medium text-neutral-200">{NAME_OVERRIDES[preset.id] ?? preset.id}</p>
      </div>
    </button>
  );
}

export function StyleGallery({
  presets,
  selectedId,
  onSelect,
}: {
  presets: StylePreset[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (presets.length === 0) {
    return <p className="text-xs text-neutral-500">Loading styles…</p>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {presets.map((preset) => (
        <PreviewCard key={preset.id} preset={preset} selected={preset.id === selectedId} onSelect={() => onSelect(preset.id)} />
      ))}
    </div>
  );
}
