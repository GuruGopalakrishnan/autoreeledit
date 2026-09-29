"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { StyleGallery } from "@/components/StyleGallery";
import { Timeline } from "@/components/Timeline";
import { CaptionInspector } from "@/components/CaptionInspector";
import {
  downloadUrl,
  getJob,
  getProject,
  getStyles,
  projectVideoUrl,
  renderProject,
  updateCaption,
  type Caption,
  type Job,
  type Project,
  type StylePreset,
} from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued…",
  transcribing: "Rendering…",
  rendering: "Rendering (person segmentation + captions)…",
  done: "Done",
  failed: "Failed",
};

export default function EditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [savingCaption, setSavingCaption] = useState(false);
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [baseStyle, setBaseStyle] = useState<string | null>(null);
  const [autoMode, setAutoMode] = useState(true);
  const [renderJob, setRenderJob] = useState<Job | null>(null);
  const [starting, setStarting] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const projectPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadProject = useCallback(async () => {
    try {
      const p = await getProject(projectId);
      setProject(p);
      if (p.status !== "transcribing" && projectPollRef.current) {
        clearInterval(projectPollRef.current);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project.");
      if (projectPollRef.current) clearInterval(projectPollRef.current);
    }
  }, [projectId]);

  useEffect(() => {
    loadProject();
    projectPollRef.current = setInterval(loadProject, 2000);
    getStyles()
      .then((d) => {
        setPresets(d.styles);
        setBaseStyle(d.defaultStyle);
      })
      .catch(() => {});
    return () => {
      if (projectPollRef.current) clearInterval(projectPollRef.current);
      if (jobPollRef.current) clearInterval(jobPollRef.current);
    };
  }, [loadProject]);

  const seekTo = useCallback((time: number) => {
    if (videoRef.current) videoRef.current.currentTime = time;
    setCurrentTime(time);
  }, []);

  const saveCaptionText = useCallback(
    async (text: string) => {
      if (selectedId === null) return;
      setSavingCaption(true);
      try {
        const { caption } = await updateCaption(projectId, selectedId, { text });
        setProject((prev) => (prev ? { ...prev, captions: prev.captions.map((c) => (c.id === caption.id ? caption : c)) } : prev));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to save caption.");
      } finally {
        setSavingCaption(false);
      }
    },
    [projectId, selectedId]
  );

  const toggleKeyword = useCallback(
    async (forceKeyword: boolean) => {
      if (selectedId === null) return;
      try {
        const { caption } = await updateCaption(projectId, selectedId, { forceKeyword });
        setProject((prev) => (prev ? { ...prev, captions: prev.captions.map((c) => (c.id === caption.id ? caption : c)) } : prev));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update caption.");
      }
    },
    [projectId, selectedId]
  );

  const startRender = useCallback(async () => {
    if (!baseStyle) return;
    setStarting(true);
    setError(null);
    try {
      const { jobId } = await renderProject(projectId, baseStyle, autoMode);
      setRenderJob({ jobId, status: "queued", progress: 0, error: null });
      jobPollRef.current = setInterval(async () => {
        try {
          const j = await getJob(jobId);
          setRenderJob(j);
          if (j.status === "done" || j.status === "failed") {
            if (jobPollRef.current) clearInterval(jobPollRef.current);
          }
        } catch {
          if (jobPollRef.current) clearInterval(jobPollRef.current);
        }
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start render.");
    } finally {
      setStarting(false);
    }
  }, [projectId, baseStyle, autoMode]);

  if (error && !project) {
    return <main className="flex min-h-screen items-center justify-center bg-[#0b0b0f] text-red-400">{error}</main>;
  }
  if (!project) {
    return <main className="flex min-h-screen items-center justify-center bg-[#0b0b0f] text-neutral-400">Loading…</main>;
  }
  if (project.status === "failed") {
    return <main className="flex min-h-screen items-center justify-center bg-[#0b0b0f] text-red-400">{project.error}</main>;
  }

  const selectedCaption: Caption | null = project.captions.find((c) => c.id === selectedId) ?? null;
  const isRendering = renderJob && renderJob.status !== "done" && renderJob.status !== "failed";

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Editor</h1>
          {project.status === "transcribing" && <span className="text-xs text-neutral-400">Transcribing speech…</span>}
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_320px]">
          <div className="space-y-5">
            <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <video
                ref={videoRef}
                src={projectVideoUrl(projectId)}
                controls
                onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                className="max-h-[60vh] w-full rounded-lg bg-black"
              />
            </section>

            <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <h2 className="mb-3 text-sm font-semibold">Timeline</h2>
              {project.status === "transcribing" ? (
                <p className="text-xs text-neutral-500">Captions will appear here once transcription finishes.</p>
              ) : (
                <Timeline
                  captions={project.captions}
                  duration={project.duration}
                  currentTime={currentTime}
                  selectedId={selectedId}
                  onSeek={seekTo}
                  onSelect={setSelectedId}
                />
              )}
            </section>

            {project.status === "ready" && (
              <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-sm font-semibold">Caption style</h2>
                  <label className="flex items-center gap-2 text-xs text-neutral-400">
                    <input type="checkbox" checked={autoMode} onChange={(e) => setAutoMode(e.target.checked)} />
                    Auto-switch for keywords &amp; fast speech
                  </label>
                </div>
                <StyleGallery presets={presets} selectedId={baseStyle} onSelect={setBaseStyle} />
              </section>
            )}

            {renderJob && (
              <section className="rounded-xl border border-white/10 bg-[#111117] p-5">
                <h2 className="mb-3 text-sm font-semibold">{renderJob.status === "failed" ? "Render failed" : "Rendering"}</h2>
                {renderJob.status !== "failed" && (
                  <>
                    <p className="mb-2 text-xs text-neutral-400">{STATUS_LABEL[renderJob.status]}</p>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-[#7c5cfc] transition-all"
                        style={{ width: `${renderJob.status === "done" ? 100 : renderJob.progress}%` }}
                      />
                    </div>
                  </>
                )}
                {renderJob.status === "failed" && <p className="text-xs text-red-400">{renderJob.error}</p>}
                {renderJob.status === "done" && (
                  <div className="mt-4">
                    {/* eslint-disable-next-line jsx-a11y/media-has-caption -- final render has no separate captions track to attach */}
                    <video src={downloadUrl(renderJob.jobId)} controls className="max-h-96 w-full rounded-lg bg-black" />
                    <a
                      href={downloadUrl(renderJob.jobId)}
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

          <div className="space-y-5">
            <CaptionInspector caption={selectedCaption} saving={savingCaption} onSave={saveCaptionText} onToggleKeyword={toggleKeyword} />

            <div className="rounded-xl border border-white/10 bg-[#111117] p-5">
              {error && <p className="mb-3 text-xs text-red-400">{error}</p>}
              <button
                onClick={startRender}
                disabled={project.status !== "ready" || !baseStyle || starting || Boolean(isRendering)}
                className="w-full rounded-lg bg-[#7c5cfc] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#6a4ce8] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isRendering ? "Rendering…" : "Export Video →"}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
