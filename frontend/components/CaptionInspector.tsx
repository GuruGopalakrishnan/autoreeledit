"use client";

import { useEffect, useState } from "react";
import type { Caption } from "@/lib/api";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = (seconds % 60).toFixed(1);
  return `${m}:${s.padStart(4, "0")}`;
}

export function CaptionInspector({
  caption,
  saving,
  onSave,
  onToggleKeyword,
}: {
  caption: Caption | null;
  saving: boolean;
  onSave: (text: string) => void;
  onToggleKeyword: (forceKeyword: boolean) => void;
}) {
  const [text, setText] = useState(caption?.text ?? "");

  useEffect(() => {
    setText(caption?.text ?? "");
  }, [caption?.id, caption?.text]);

  if (!caption) {
    return (
      <div className="rounded-xl border border-white/10 bg-[#111117] p-5">
        <h2 className="mb-1 text-sm font-semibold">Caption Inspector</h2>
        <p className="text-xs text-neutral-500">Click a caption on the timeline to edit its text or force it to Dramatic style.</p>
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
        <input
          type="checkbox"
          checked={caption.isKeyword}
          onChange={(e) => onToggleKeyword(e.target.checked)}
        />
      </label>
      <p className="mt-1 text-[10px] text-neutral-600">
        Makes this caption punch into the huge full-frame Dramatic style regardless of its wording.
      </p>
    </div>
  );
}
