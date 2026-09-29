"use client";

import { useEffect, useState } from "react";
import type { Caption, StylePreset } from "@/lib/api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}

const MOMENT_LABELS: Record<string, string> = {
  "cutout-title": "Cutout Title",
  "black-pause": "Black Pause",
  "starburst-moment": "Starburst",
};

export function CaptionInspector({
  caption,
  saving,
  titleMoments,
  onSave,
  onToggleKeyword,
  onSelectTitleMoment,
}: {
  caption: Caption | null;
  saving: boolean;
  titleMoments: StylePreset[];
  onSave: (text: string) => void;
  onToggleKeyword: (forceKeyword: boolean) => void;
  onSelectTitleMoment: (id: string | null) => void;
}) {
  const [text, setText] = useState(caption?.text ?? "");

  useEffect(() => {
    setText(caption?.text ?? "");
  }, [caption?.id, caption?.text]);

  if (!caption) {
    return (
      <div className="rounded-xl border border-white/10 bg-[#111117] p-5">
        <h2 className="mb-1 text-sm font-semibold">Caption Inspector</h2>
        <p className="text-xs text-neutral-500">Click a caption on the timeline to edit its text, force Dramatic, or apply a Title Moment.</p>
      </div>
    );
  }

  const dirty = text !== caption.text;

  return (
    <div className="rounded-xl border border-white/10 bg-[#111117] p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Caption Inspector</h2>
        <span className="font-mono text-[10px] text-neutral-500">
          {formatTime(caption.start)} – {formatTime(caption.end)}
        </span>
      </div>

      <label className="mb-1 block text-xs font-medium text-neutral-300">Text</label>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={3}
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white focus:border-white/40 focus:outline-none"
      />
      <button
        onClick={() => onSave(text)}
        disabled={!dirty || saving}
        className="mt-2 w-full rounded-lg bg-[#7c5cfc] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#6a4ce8] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {saving ? "Saving…" : "Save Text"}
      </button>

      <label className="mt-4 flex items-center justify-between text-xs text-neutral-300">
        Force Dramatic style
        <input type="checkbox" checked={caption.isKeyword} onChange={(e) => onToggleKeyword(e.target.checked)} disabled={Boolean(caption.titleMoment)} />
      </label>
      <p className="mt-1 text-[10px] text-neutral-600">Makes this caption punch into the huge full-frame Dramatic style regardless of its wording.</p>

      <div className="mt-4 border-t border-white/10 pt-4">
        <p className="mb-2 text-xs font-medium text-neutral-300">Title Moment</p>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            onClick={() => onSelectTitleMoment(null)}
            className={`rounded-lg border px-2 py-2 text-xs ${
              !caption.titleMoment ? "border-[#7c5cfc] bg-[#7c5cfc]/10 text-white" : "border-white/10 text-neutral-400 hover:border-white/25"
            }`}
          >
            None
          </button>
          {titleMoments.map((m) => (
            <button
              key={m.id}
              onClick={() => onSelectTitleMoment(m.id)}
              className={`rounded-lg border px-2 py-2 text-xs ${
                caption.titleMoment === m.id ? "border-[#7c5cfc] bg-[#7c5cfc]/10 text-white" : "border-white/10 text-neutral-400 hover:border-white/25"
              }`}
            >
              {MOMENT_LABELS[m.id] ?? m.id}
            </button>
          ))}
        </div>
        <p className="mt-2 text-[10px] text-neutral-600">
          Overrides everything else for this one caption -- e.g. Cutout Title puts the text behind the person with a red outline; Black Pause cuts to black.
        </p>
      </div>
    </div>
  );
}
