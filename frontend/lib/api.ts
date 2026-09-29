export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type JobStatus = "queued" | "transcribing" | "rendering" | "done" | "failed";

export type Job = {
  jobId: string;
  status: JobStatus;
  progress: number;
  error: string | null;
};

// Mirrors backend/pipeline/caption_engine.py's StyleConfig -- one entry per
// non-reserved preset in config.json's `styles`.
export type StylePreset = {
  id: string;
  font: string;
  font_size: number;
  color: string;
  outline_color: string | null;
  outline_width: number;
  bg_color: string | null;
  position: string;
  animation: "word_fade_in" | "scale_punch_in" | "slide_in" | "typewriter";
};

export async function getStyles(): Promise<{ styles: StylePreset[]; defaultStyle: string }> {
  const res = await fetch(`${API_BASE}/api/styles`);
  if (!res.ok) throw new Error("Failed to load style presets.");
  return res.json();
}

export async function createJob(
  video: File,
  baseStyle: string,
  autoMode: boolean,
  transcript?: File | null
): Promise<{ jobId: string }> {
  const formData = new FormData();
  formData.append("video", video);
  formData.append("base_style", baseStyle);
  formData.append("auto_mode", String(autoMode));
  if (transcript) formData.append("transcript", transcript);
  const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to start the job.");
  return data;
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Job not found.");
  return data;
}

export function downloadUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/download`;
}
