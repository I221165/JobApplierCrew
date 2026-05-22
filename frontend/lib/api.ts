import type {
  ApplyResponse,
  Application,
  Job,
  NotificationWithJob,
  SavedSearch,
  ScreenResponse,
  SearchResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  async parseCv(file: File): Promise<{ text: string; pages: number }> {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_URL}/cv/parse`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  },

  search(role: string, location: string, max_jobs = 5): Promise<SearchResponse> {
    return fetchJson("/search", {
      method: "POST",
      body: JSON.stringify({ role, location, max_jobs }),
    });
  },

  listJobs(role?: string, location?: string): Promise<Job[]> {
    const params = new URLSearchParams();
    if (role) params.append("role", role);
    if (location) params.append("location", location);
    const qs = params.toString();
    return fetchJson(`/jobs${qs ? "?" + qs : ""}`);
  },

  getJob(id: string): Promise<Job> {
    return fetchJson(`/jobs/${id}`);
  },

  screenJob(id: string, cv: string): Promise<ScreenResponse> {
    return fetchJson(`/jobs/${id}/screen`, {
      method: "POST",
      body: JSON.stringify({ cv }),
    });
  },

  applyJob(id: string, cv: string, latex_template?: string): Promise<ApplyResponse> {
    return fetchJson(`/jobs/${id}/apply`, {
      method: "POST",
      body: JSON.stringify({ cv, latex_template: latex_template ?? null }),
    });
  },

  getApplication(id: string): Promise<Application> {
    return fetchJson(`/applications/${id}`);
  },

  streamApplicationUrl(id: string): string {
    return `${API_URL}/applications/${id}/stream`;
  },

  pdfUrl(id: string): string {
    return `${API_URL}/applications/${id}/pdf`;
  },

  // Saved searches
  createSavedSearch(role: string, location: string, cv: string, max_jobs = 5, min_score = 60): Promise<{ id: string }> {
    return fetchJson("/searches", {
      method: "POST",
      body: JSON.stringify({ role, location, cv, max_jobs, min_score }),
    });
  },

  listSavedSearches(): Promise<SavedSearch[]> {
    return fetchJson("/searches");
  },

  deleteSavedSearch(id: string): Promise<{ status: string }> {
    return fetchJson(`/searches/${id}`, { method: "DELETE" });
  },

  runSavedSearchNow(id: string): Promise<{ status: string }> {
    return fetchJson(`/searches/${id}/run`, { method: "POST" });
  },

  // Notifications
  listNotifications(unreadOnly = false): Promise<NotificationWithJob[]> {
    return fetchJson(`/notifications${unreadOnly ? "?unread_only=true" : ""}`);
  },

  markNotificationRead(id: string): Promise<{ status: string }> {
    return fetchJson(`/notifications/${id}/read`, { method: "POST" });
  },
};
