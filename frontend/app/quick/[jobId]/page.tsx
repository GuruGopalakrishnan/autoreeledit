"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { downloadUrl, getJob, type Job } from "@/lib/api";
import { styleDisplayName } from "@/lib/styleNames";

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued…",
  transcribing: "Transcribing speech…",
  rendering: "Rendering (AI-picked style, person segmentation, captions)…",
  done: "Done",
  failed: "Failed",
};

export default function QuickExportResultPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const j = await getJob(jobId);
        setJob(j);
        if (j.status === "done" || j.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load job status.");
        if (pollRef.current) clearInterval(pollRef.current);
      }
    };
    poll();
    pollRef.current = setInterval(poll, 1500);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [jobId]);

  const isActive = job && job.status !== "done" && job.status !== "failed";

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-6">
        <div className="mb-6">
          <h1 className="text-xl font-semibold">Auto-Export</h1>
          <p className="text-xs text-neutral-500">AI picked the caption style from your transcript -- no editor step.</p>
        </div>

        <div className="mx-auto max-w-lg space-y-5">
          {error && (
            <div className="rounded-xl border border-red-900/50 bg-red-950/30 p-5 text-sm text-red-400">{error}</div>
          )}

          {!job && !error && (
            <div className="rounded-xl border border-white/10 bg-[#111117] p-5 text-sm text-neutral-400">Loading…</div>
          )}

          {job && job.status !== "failed" && (
            <div className="rounded-xl border border-white/10 bg-[#111117] p-5">
              <h2 className="mb-3 text-sm font-semibold">{isActive ? "Rendering" : "Done"}</h2>
              {isActive && (
                <>
                  <p className="mb-2 text-xs text-neutral-400">{STATUS_LABEL[job.status]}</p>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-[#7c5cfc] transition-all"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </>
              )}

              {job.status === "done" && (
                <div>
                  {job.styleUsed && (
                    <p className="mb-3 inline-block rounded-full border border-[#7c5cfc]/40 bg-[#7c5cfc]/10 px-3 py-1 text-xs text-[#a993ff]">
                      AI picked: <span className="font-semibold">{styleDisplayName(job.styleUsed)}</span>
                    </p>
                  )}
                  {/* eslint-disable-next-line jsx-a11y/media-has-caption -- final render has no separate captions track to attach */}
                  <video src={downloadUrl(job.jobId)} controls className="w-full rounded-lg bg-black" />
                  <a
                    href={downloadUrl(job.jobId)}
                    download
                    className="mt-3 inline-block rounded-lg bg-[#7c5cfc] px-4 py-2 text-sm font-medium text-white hover:bg-[#6a4ce8]"
                  >
                    Download Video
                  </a>
                </div>
              )}
            </div>
          )}

          {job?.status === "failed" && (
            <div className="rounded-xl border border-red-900/50 bg-red-950/30 p-5">
              <h2 className="mb-2 text-sm font-semibold text-red-400">Render failed</h2>
              <p className="text-xs text-red-400">{job.error}</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
