"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { getCV } from "@/lib/cv";
import { JobCard } from "./components/JobCard";

const STORAGE_KEY = "job_applier_last_search";
const PASS_THRESHOLD = 60;

interface SavedSearch {
  role: string;
  location: string;
  maxJobs: number;
  jobIds: string[];
}

export default function HomePage() {
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [maxJobs, setMaxJobs] = useState(5);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasCV, setHasCV] = useState(true);

  const [batchScreening, setBatchScreening] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ done: 0, total: 0 });
  const [onlyPasses, setOnlyPasses] = useState(false);

  useEffect(() => {
    setHasCV(getCV().trim().length > 0);
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    try {
      const parsed: SavedSearch = JSON.parse(saved);
      setRole(parsed.role);
      setLocation(parsed.location);
      setMaxJobs(parsed.maxJobs ?? 5);
      if (parsed.jobIds?.length) {
        Promise.all(parsed.jobIds.map((id) => api.getJob(id).catch(() => null)))
          .then((results) => setJobs(results.filter((j): j is Job => j !== null)));
      }
    } catch {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  async function handleSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setJobs([]);
    try {
      const { job_ids } = await api.search(role.trim(), location.trim(), maxJobs);
      const fetched = await Promise.all(job_ids.map((id) => api.getJob(id)));
      setJobs(fetched);
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ role: role.trim(), location: location.trim(), maxJobs, jobIds: job_ids } satisfies SavedSearch),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleScreenAll() {
    const cv = getCV();
    if (!cv.trim()) {
      setError("Add your CV first (CV tab in the nav).");
      return;
    }
    const unscreened = jobs.filter((j) => j.match_score === null);
    if (unscreened.length === 0) return;

    setError(null);
    setBatchScreening(true);
    setBatchProgress({ done: 0, total: unscreened.length });

    for (let i = 0; i < unscreened.length; i++) {
      try {
        await api.screenJob(unscreened[i].id, cv);
        const updated = await api.getJob(unscreened[i].id);
        setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      } catch (err) {
        console.error(`Failed to screen ${unscreened[i].id}:`, err);
      }
      setBatchProgress({ done: i + 1, total: unscreened.length });
    }

    setBatchScreening(false);
    setOnlyPasses(true);
  }

  function clearResults() {
    setJobs([]);
    sessionStorage.removeItem(STORAGE_KEY);
    setOnlyPasses(false);
  }

  const unscreenedCount = jobs.filter((j) => j.match_score === null).length;
  const passedCount = jobs.filter(
    (j) => j.is_active && j.role_match && (j.match_score ?? 0) >= PASS_THRESHOLD,
  ).length;

  const visibleJobs = jobs
    .filter((j) => {
      if (!onlyPasses) return true;
      return j.is_active && j.role_match && (j.match_score ?? 0) >= PASS_THRESHOLD;
    })
    .slice()
    .sort((a, b) => (b.match_score ?? -1) - (a.match_score ?? -1));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Search jobs</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Search LinkedIn, Indeed, and Rozee for open roles in the last 30 days.
        </p>
      </div>

      {!hasCV && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
          <p className="text-amber-900">
            You haven&apos;t saved a CV yet.{" "}
            <Link href="/cv" className="font-medium underline">
              Add your CV
            </Link>{" "}
            before screening or applying.
          </p>
        </div>
      )}

      <form onSubmit={handleSearch} className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3">
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Role</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="DevOps Engineer"
              required
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Location</label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Islamabad, Pakistan"
              required
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Max jobs</label>
            <select
              value={maxJobs}
              onChange={(e) => setMaxJobs(Number(e.target.value))}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search"}
          </button>
          {jobs.length > 0 && (
            <button
              type="button"
              onClick={clearResults}
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
            >
              Clear
            </button>
          )}
        </div>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
          {error}
        </div>
      )}

      {loading && (
        <div className="grid gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg border border-neutral-200 bg-white p-4 animate-pulse">
              <div className="h-4 bg-neutral-200 rounded w-3/4 mb-3" />
              <div className="h-3 bg-neutral-100 rounded w-full mb-1" />
              <div className="h-3 bg-neutral-100 rounded w-5/6" />
            </div>
          ))}
        </div>
      )}

      {!loading && jobs.length > 0 && (
        <div className="space-y-3">
          {/* Action bar: screen-all + filter toggle */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-neutral-200 bg-white p-3">
            <div className="flex items-center gap-3">
              {unscreenedCount > 0 ? (
                <button
                  onClick={handleScreenAll}
                  disabled={batchScreening || !hasCV}
                  className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                >
                  {batchScreening
                    ? `Screening ${batchProgress.done}/${batchProgress.total}...`
                    : `Screen all (${unscreenedCount})`}
                </button>
              ) : (
                <span className="text-sm text-neutral-500">All jobs screened</span>
              )}
              <span className="text-sm text-neutral-700">
                <span className="font-medium text-emerald-700">{passedCount}</span> passed
                <span className="text-neutral-400"> / {jobs.length} total</span>
              </span>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={onlyPasses}
                onChange={(e) => setOnlyPasses(e.target.checked)}
                className="rounded border-neutral-300"
              />
              Only show passes
            </label>
          </div>

          {/* Batch screening progress bar */}
          {batchScreening && (
            <div className="h-1 w-full rounded-full bg-neutral-200 overflow-hidden">
              <div
                className="h-full bg-emerald-500 transition-all"
                style={{ width: `${(batchProgress.done / batchProgress.total) * 100}%` }}
              />
            </div>
          )}

          {/* Job list */}
          <div className="grid gap-3">
            {visibleJobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>

          {visibleJobs.length === 0 && (
            <div className="rounded-lg border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
              {onlyPasses ? "No jobs passed the threshold yet. Run Screen all, or uncheck the filter." : "No jobs."}
            </div>
          )}
        </div>
      )}

      {!loading && jobs.length === 0 && role && (
        <div className="rounded-lg border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          No results yet. Click Search to begin.
        </div>
      )}
    </div>
  );
}
