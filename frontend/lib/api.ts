export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type JobStatus = "queued" | "transcribing" | "rendering" | "done" | "failed";

export type Job = {
  jobId: string;
  status: JobStatus;
  progress: number;
  error: string | null;
  styleUsed?: string | null;
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

export async function getTitleMoments(): Promise<{ moments: StylePreset[] }> {
  const res = await fetch(`${API_BASE}/api/title-moments`);
  if (!res.ok) throw new Error("Failed to load title moments.");
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

// --- Editor (Phase 3): upload -> transcribe once -> review/edit captions on
// a timeline -> render when ready. -----------------------------------------

export type ProjectStatus = "transcribing" | "ready" | "failed";

export type Caption = {
  id: number;
  start: number;
  end: number;
  text: string;
  isKeyword: boolean;
  titleMoment: string | null;
};

export type Project = {
  id: string;
  status: ProjectStatus;
  error: string | null;
  duration: number;
  width: number;
  height: number;
  captions: Caption[];
};

export async function createProject(video: File, transcript?: File | null): Promise<{ projectId: string }> {
  const formData = new FormData();
  formData.append("video", video);
  if (transcript) formData.append("transcript", transcript);
  const res = await fetch(`${API_BASE}/api/projects`, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to create the project.");
  return data;
}

export async function getProject(projectId: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Project not found.");
  return data;
}

export function projectVideoUrl(projectId: string): string {
  return `${API_BASE}/api/projects/${projectId}/video`;
}

export async function updateCaption(
  projectId: string,
  cueId: number,
  patch: { text?: string; forceKeyword?: boolean; titleMoment?: string | null }
): Promise<{ caption: Caption }> {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/captions/${cueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to update the caption.");
  return data;
}

export async function renderProject(
  projectId: string,
  baseStyle: string,
  autoMode: boolean,
  trackHands: boolean = true
): Promise<{ jobId: string }> {
  const formData = new FormData();
  formData.append("base_style", baseStyle);
  formData.append("auto_mode", String(autoMode));
  formData.append("track_hands", String(trackHands));
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/render`, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to start the render.");
  return data;
}
