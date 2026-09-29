export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type JobStatus = "queued" | "transcribing" | "rendering" | "done" | "failed";

export type Job = {
  jobId: string;
  status: JobStatus;
  progress: number;
  error: string | null;
};

export type Style = "auto" | "casual" | "dramatic" | "energetic" | "minimal";

export async function createJob(video: File, style: Style): Promise<{ jobId: string }> {
  const formData = new FormData();
  formData.append("video", video);
  formData.append("style", style);
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
