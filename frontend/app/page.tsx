"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { createJob, createProject } from "@/lib/api";

export default function ProjectSetupPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [transcriptText, setTranscriptText] = useState("");
  const [transcriptMode, setTranscriptMode] = useState<"upload" | "paste">("upload");
  const [starting, setStarting] = useState(false);
  const [autoStarting, setAutoStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  const onSelectFile = useCallback((f: File) => {
    setFile(f);
    setVideoUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(f);
    });
    setError(null);
  }, []);

  const resolveTranscript = useCallback((): File | null => {
    return transcriptMode === "paste" && transcriptText.trim()
      ? new File([transcriptText], "pasted.srt", { type: "text/plain" })
      : transcriptFile;
  }, [transcriptFile, transcriptMode, transcriptText]);

  const startProject = useCallback(async () => {
    if (!file) return;
    setStarting(true);
    setError(null);
    try {
      const { projectId } = await createProject(file, resolveTranscript());
      router.push(`/editor/${projectId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create the project.");
      setStarting(false);
    }
  }, [file, resolveTranscript, router]);

  const startAutoExport = useCallback(async () => {
    if (!file) return;
    setAutoStarting(true);
    setError(null);
    try {
      const { jobId } = await createJob(file, "auto", true, resolveTranscript());
      router.push(`/quick/${jobId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start the export.");
      setAutoStarting(false);
    }
  }, [file, resolveTranscript, router]);

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">
            Project: <span className="text-neutral-300">Untitled Talking-Head Video</span>
          </h1>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
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
                <h2 className="text-sm font-semibold">Timestamped transcript (optional)</h2>
              </div>
              <p className="mb-3 text-xs text-neutral-500">
                Skips Whisper entirely, so captions match your exact words. Without one, speech is auto-transcribed.
              </p>

              <div className="mb-3 flex gap-1.5">
                <button
                  onClick={() => setTranscriptMode("upload")}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    transcriptMode === "upload" ? "border-white bg-white text-black" : "border-white/15 text-neutral-300 hover:border-white/40"
                  }`}
                >
                  Upload file
                </button>
                <button
                  onClick={() => setTranscriptMode("paste")}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    transcriptMode === "paste" ? "border-white bg-white text-black" : "border-white/15 text-neutral-300 hover:border-white/40"
                  }`}
                >
                  Paste text
                </button>
              </div>

              {transcriptMode === "upload" ? (
                transcriptFile ? (
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
                )
              ) : (
                <div>
                  <textarea
                    value={transcriptText}
                    onChange={(e) => setTranscriptText(e.target.value)}
                    rows={6}
                    placeholder={"(0:00) Ok, I am going to test this video. (0:04) Lets see how it works.\n\nOr paste real SRT format — both work."}
                    className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-xs text-white placeholder:text-neutral-600 focus:border-white/40 focus:outline-none"
                  />
                  <p className="mt-1.5 text-[10px] text-neutral-600">
                    Add a <code className="rounded bg-white/10 px-1 py-0.5">(0:04)</code> timestamp before each sentence, or paste SRT-formatted text directly.
                  </p>
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
          </div>

          <aside className="h-fit rounded-xl border border-white/10 bg-[#111117] p-5">
            <h2 className="mb-1 text-sm font-semibold">Next</h2>
            <p className="mb-4 text-xs text-neutral-500">
              Auto-export picks a caption style from the transcript itself (energy, pace, multiple speakers) and
              renders straight away -- no editor step. Open Editor lets you review captions and pick a style by hand.
            </p>

            {error && <p className="mb-3 text-xs text-red-400">{error}</p>}

            <button
              onClick={startAutoExport}
              disabled={!file || autoStarting || starting}
              className="w-full rounded-lg bg-[#7c5cfc] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a4ce8] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {autoStarting ? "Starting…" : "Auto-Export (AI picks style) →"}
            </button>

            <button
              onClick={startProject}
              disabled={!file || starting || autoStarting}
              className="mt-2 w-full rounded-lg border border-white/15 px-4 py-2.5 text-sm font-medium text-neutral-200 hover:border-white/30 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {starting ? "Creating…" : "Open Editor →"}
            </button>
          </aside>
        </div>
      </main>
    </div>
  );
}
