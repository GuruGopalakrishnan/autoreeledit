"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { createJob, downloadUrl, getJob, type Job, type Style } from "@/lib/api";

const STYLES: { value: Style; label: string; description: string }[] = [
  { value: "auto", label: "Auto (Recommended)", description: "Switches style automatically: keywords trigger Dramatic, fast speech triggers Energetic." },
  { value: "casual", label: "Casual", description: "Clean lower-third captions, word-by-word fade in." },
  { value: "dramatic", label: "Dramatic", description: "Huge keyword text takes over the frame." },
  { value: "energetic", label: "Energetic", description: "Colorful badge captions beside the person." },
  { value: "minimal", label: "Minimal", description: "Small top-of-frame typewriter captions." },
];

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued…",
  transcribing: "Reading transcript…",
  rendering: "Rendering (person segmentation + captions)…",
  done: "Done",
  failed: "Failed",
};

export default function ProjectSetupPage() {
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [style, setStyle] = useState<Style>("auto");
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const onSelectFile = useCallback((f: File) => {
    setFile(f);
    setVideoUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
    setJob(null);
    setError(null);
  }, []);

  const pollJob = useCallback((jobId: string) => {
    pollRef.current = setInterval(async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        if (j.status === "done" || j.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
      }
    }, 1500);
  }, []);

  const startProcessing = useCallback(async () => {
    if (!file) return;
    setStarting(true);
    setError(null);
    try {
      const { jobId } = await createJob(file, style, transcriptFile);
      setJob({ jobId, status: "queued", progress: 0, error: null });
      pollJob(jobId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start processing.");
    } finally {
      setStarting(false);
    }
  }, [file, style, transcriptFile, pollJob]);

  const isProcessing = job && job.status !== "done" && job.status !== "failed";

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">
            Project: <span className="text-neutral-300">Untitled Talking-Head Video</span>
          </h1>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_360px]">
          <div className="space-y-5">
            <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#7c5cfc] text-xs font-bold">1</span>
                <h2 className="text-sm font-semibold">Upload video</h2>
              </div>
              <p className="mb-3 text-xs text-neutral-500">Add your talking-head video (MP4, MOV, or similar).</p>

              {videoUrl ? (
                <div>
                  {/* eslint-disable-next-line jsx-a11y/media-has-caption -- local preview of the user's own upload, no captions source available */}
                  <video src={videoUrl} controls className="max-h-80 w-full rounded-lg bg-black" />
                  <div className="mt-2 flex items-center justify-between">
                    <p className="truncate text-xs text-neutral-400">{file?.name}</p>
                    <button onClick={() => inputRef.current?.click()} className="text-xs text-[#a993ff] hover:underline">
                      Replace
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files?.[0];
                    if (f) onSelectFile(f);
                  }}
                  className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-white/15 p-12 text-center hover:border-white/30"
                >
                  <p className="text-sm text-neutral-300">Drop a video here, or click to browse</p>
                  <p className="mt-1 text-xs text-neutral-600">MP4, MOV, WEBM</p>
                </div>
              )}
              <input
                ref={inputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onSelectFile(f);
                }}
              />
            </section>

            <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <div className="mb-3 flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#7c5cfc] text-xs font-bold">2</span>
                <h2 className="text-sm font-semibold">Upload timestamped transcript (optional)</h2>
              </div>
              <p className="mb-3 text-xs text-neutral-500">
                Add an SRT file with timestamps. Skips Whisper entirely, so captions match your exact words. Without one, speech is auto-transcribed.
              </p>

              {transcriptFile ? (
                <div className="flex items-center justify-between rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                  <span className="truncate text-xs text-neutral-300">{transcriptFile.name}</span>
                  <div className="flex shrink-0 gap-2">
                    <button onClick={() => transcriptInputRef.current?.click()} className="text-xs text-[#a993ff] hover:underline">
                      Replace
                    </button>
                    <button onClick={() => setTranscriptFile(null)} className="text-xs text-neutral-500 hover:text-red-400">
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => transcriptInputRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    const f = e.dataTransfer.files?.[0];
                    if (f) setTranscriptFile(f);
                  }}
                  className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-white/15 p-6 text-center hover:border-white/30"
                >
                  <p className="text-xs text-neutral-400">Drop an .srt file here, or click to browse</p>
                </div>
              )}
              <input
                ref={transcriptInputRef}
                type="file"
                accept=".srt"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) setTranscriptFile(f);
                }}
              />
            </section>

            {job && (
              <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
                <h2 className="mb-3 text-sm font-semibold">
                  {job.status === "failed" ? "Processing failed" : "Auto prepare"}
                </h2>

                {job.status !== "failed" && (
                  <>
                    <p className="mb-2 text-xs text-neutral-400">{STATUS_LABEL[job.status]}</p>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-[#7c5cfc] transition-all"
                        style={{ width: `${job.status === "done" ? 100 : job.progress}%` }}
                      />
                    </div>
                  </>
                )}

                {job.status === "failed" && <p className="text-xs text-red-400">{job.error}</p>}

                {job.status === "done" && (
                  <div className="mt-4">
                    {/* eslint-disable-next-line jsx-a11y/media-has-caption -- final render has no separate captions track to attach */}
                    <video src={downloadUrl(job.jobId)} controls className="max-h-96 w-full rounded-lg bg-black" />
                    <a
                      href={downloadUrl(job.jobId)}
                      download
                      className="mt-3 inline-block rounded-lg bg-[#7c5cfc] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a4ce8]"
                    >
                      Download Video
                    </a>
                  </div>
                )}
              </section>
            )}
          </div>

          <aside className="rounded-xl border border-white/10 bg-[#111117] p-5">
            <h2 className="mb-1 text-sm font-semibold">Output settings</h2>
            <p className="mb-4 text-xs text-neutral-500">Configure your editing project</p>

            <p className="mb-2 text-xs font-medium text-neutral-300">Caption Style</p>
            <div className="space-y-1.5">
              {STYLES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStyle(s.value)}
                  className={`w-full rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                    style === s.value ? "border-[#7c5cfc] bg-[#7c5cfc]/10" : "border-white/10 hover:border-white/25"
                  }`}
                >
                  <p className="font-medium text-neutral-200">{s.label}</p>
                  <p className="mt-0.5 text-[10px] text-neutral-500">{s.description}</p>
                </button>
              ))}
            </div>

            {error && <p className="mt-3 text-xs text-red-400">{error}</p>}

            <button
              onClick={startProcessing}
              disabled={!file || starting || Boolean(isProcessing)}
              className="mt-5 w-full rounded-lg bg-[#7c5cfc] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a4ce8] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isProcessing ? "Processing…" : "Create Editing Project →"}
            </button>
            <p className="mt-2 text-[10px] text-neutral-600">
              {transcriptFile
                ? "Using your uploaded transcript — Whisper is skipped."
                : "We'll transcribe your speech, segment the person from the background, and render animated captions automatically."}
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}
