"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SavedSearch } from "@/lib/types";
import { getCV } from "@/lib/cv";

export default function SearchesPage() {
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form
  const [role, setRole] = useState("");
  const [location, setLocation] = useState("");
  const [maxJobs, setMaxJobs] = useState(5);
  const [minScore, setMinScore] = useState(60);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      setSearches(await api.listSavedSearches());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const cv = getCV();
    if (!cv.trim()) {
      setError("Add your CV first (CV tab in nav) — saved searches need a frozen CV snapshot.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await api.createSavedSearch(role.trim(), location.trim(), cv, maxJobs, minScore);
      setRole("");
      setLocation("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this saved search?")) return;
    await api.deleteSavedSearch(id);
    await load();
  }

  async function handleRunNow(id: string) {
    setError(null);
    try {
      const { status } = await api.runSavedSearchNow(id);
      await load();
      alert(`Run complete: ${status}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Saved searches</h1>
        <p className="mt-1 text-sm text-neutral-600">
          The scheduler runs each of these once every 24 hours. New jobs above the minimum match score
          appear in <Link href="/notifications" className="underline">notifications</Link>.
        </p>
      </div>

      <form onSubmit={handleCreate} className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
        <h2 className="text-sm font-medium">Add a saved search</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-neutral-700 mb-1">Role</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              required
              placeholder="DevOps Engineer"
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-neutral-700 mb-1">Location</label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              required
              placeholder="Islamabad, Pakistan"
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Max jobs</label>
            <select
              value={maxJobs}
              onChange={(e) => setMaxJobs(Number(e.target.value))}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm bg-white"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-neutral-700 mb-1">Min match %</label>
            <input
              type="number"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={saving}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Add"}
        </button>
        <p className="text-xs text-neutral-500">
          A copy of your CV is frozen at save time, so background runs use this version regardless of edits later.
        </p>
      </form>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-neutral-500">Loading...</p>
      ) : searches.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          No saved searches yet. Add one above to start receiving daily notifications.
        </div>
      ) : (
        <div className="grid gap-3">
          {searches.map((s) => (
            <div key={s.id} className="rounded-lg border border-neutral-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">
                    {s.role} <span className="text-neutral-500 font-normal">in {s.location}</span>
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Max {s.max_jobs} jobs · Min {s.min_score}% match
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    Last run: {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "never"}
                    {s.last_run_status && (
                      <span className={`ml-2 ${s.last_run_status.startsWith("ok") ? "text-emerald-600" : "text-rose-600"}`}>
                        {s.last_run_status}
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleRunNow(s.id)}
                    className="rounded-md border border-neutral-300 px-3 py-1 text-xs font-medium hover:bg-neutral-50"
                  >
                    Run now
                  </button>
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="rounded-md border border-rose-300 px-3 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
