"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { StyleGallery } from "@/components/StyleGallery";
import { createJob, downloadUrl, getJob, getStyles, type Job, type StylePreset } from "@/lib/api";

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
  const [transcriptText, setTranscriptText] = useState("");
  const [transcriptMode, setTranscriptMode] = useState<"upload" | "paste">("upload");
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [baseStyle, setBaseStyle] = useState<string | null>(null);
  const [autoMode, setAutoMode] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getStyles()
      .then((d) => {
        setPresets(d.styles);
        setBaseStyle(d.defaultStyle);
      })
      .catch(() => {});
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
    if (!file || !baseStyle) return;
    setStarting(true);
    setError(null);
    try {
      const transcript =
        transcriptMode === "paste" && transcriptText.trim()
          ? new File([transcriptText], "pasted.srt", { type: "text/plain" })
          : transcriptFile;
      const { jobId } = await createJob(file, baseStyle, autoMode, transcript);
      setJob({ jobId, status: "queued", progress: 0, error: null });
      pollJob(jobId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start processing.");
    } finally {
      setStarting(false);
    }
  }, [file, baseStyle, autoMode, transcriptFile, transcriptMode, transcriptText, pollJob]);

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

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_320px]">
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

            <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#7c5cfc] text-xs font-bold">3</span>
                  <h2 className="text-sm font-semibold">Choose a caption style</h2>
                </div>
                <label className="flex items-center gap-2 text-xs text-neutral-400">
                  <input type="checkbox" checked={autoMode} onChange={(e) => setAutoMode(e.target.checked)} />
                  Auto-switch for keywords &amp; fast speech
                </label>
              </div>
              <p className="mb-3 text-xs text-neutral-500">
                This is the base look for ordinary captions.
                {autoMode ? " Keyword moments still punch into the huge Dramatic style automatically, and fast speech into Energetic." : " Auto-switching is off, so this style is the only one that ever shows."}
              </p>
              <StyleGallery presets={presets} selectedId={baseStyle} onSelect={setBaseStyle} />
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

          <aside className="h-fit rounded-xl border border-white/10 bg-[#111117] p-5">
            <h2 className="mb-1 text-sm font-semibold">Output settings</h2>
            <p className="mb-4 text-xs text-neutral-500">Configure your editing project</p>

            {error && <p className="mb-3 text-xs text-red-400">{error}</p>}

            <button
              onClick={startProcessing}
              disabled={!file || !baseStyle || starting || Boolean(isProcessing)}
              className="w-full rounded-lg bg-[#7c5cfc] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a4ce8] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isProcessing ? "Processing…" : "Create Editing Project →"}
            </button>
            <p className="mt-2 text-[10px] text-neutral-600">
              {(transcriptMode === "upload" && transcriptFile) || (transcriptMode === "paste" && transcriptText.trim())
                ? "Using your transcript — Whisper is skipped."
                : "We'll transcribe your speech, segment the person from the background, and render animated captions automatically."}
            </p>
          </aside>
        </div>
      </main>
    </div>
  );
}
