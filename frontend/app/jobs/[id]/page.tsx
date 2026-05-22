"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { getCV, getLatexTemplate } from "@/lib/cv";
import { ScoreBadge } from "@/app/components/ScoreBadge";

export default function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [screening, setScreening] = useState(false);
  const [applying, setApplying] = useState(false);

  async function load() {
    try {
      setJob(await api.getJob(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function handleScreen() {
    const cv = getCV();
    if (!cv.trim()) {
      setError("Add your CV first (click 'CV' in the nav).");
      return;
    }
    setError(null);
    setScreening(true);
    try {
      await api.screenJob(id, cv);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setScreening(false);
    }
  }

  async function handleApply() {
    const cv = getCV();
    if (!cv.trim()) {
      setError("Add your CV first.");
      return;
    }
    setError(null);
    setApplying(true);
    try {
      const tmpl = getLatexTemplate();
      const { application_id } = await api.applyJob(id, cv, tmpl || undefined);
      router.push(`/applications/${application_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setApplying(false);
    }
  }

  if (loading) return <p className="text-sm text-neutral-500">Loading...</p>;
  if (error && !job) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</div>
    );
  }
  if (!job) return null;

  const mustHave: string[] = job.must_have_json ? JSON.parse(job.must_have_json) : [];
  const niceToHave: string[] = job.nice_to_have_json ? JSON.parse(job.nice_to_have_json) : [];
  const isScreened = job.match_score !== null;

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-neutral-600 hover:text-neutral-900">
        ← Back to search
      </Link>

      <div className="rounded-lg border border-neutral-200 bg-white p-5 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl font-semibold leading-tight">{job.title}</h1>
          <ScoreBadge score={job.match_score} />
        </div>
        {job.actual_title && job.actual_title !== job.title && (
          <p className="text-sm text-neutral-600">Actual title: <span className="font-medium">{job.actual_title}</span></p>
        )}
        <p className="text-sm text-neutral-700">{job.snippet}</p>
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block text-sm text-sky-700 hover:text-sky-900 break-all"
        >
          {job.url}
        </a>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</div>
      )}

      {!isScreened ? (
        <button
          onClick={handleScreen}
          disabled={screening}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800 disabled:opacity-50"
        >
          {screening ? "Screening..." : "Screen this job"}
        </button>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <Stat label="Status" value={job.is_active ? "Active" : "Closed"} color={job.is_active ? "emerald" : "rose"} />
            <Stat label="Role match" value={job.role_match ? "Yes" : "No"} color={job.role_match ? "emerald" : "rose"} />
            <Stat label="Tone" value={job.tone || "—"} />
          </div>

          {mustHave.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-neutral-700 mb-2">Must-have requirements</h3>
              <ul className="space-y-1 text-sm">
                {mustHave.map((req, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-neutral-400">•</span>
                    <span>{req}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {niceToHave.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-neutral-700 mb-2">Nice to have</h3>
              <ul className="space-y-1 text-sm text-neutral-600">
                {niceToHave.map((req, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-neutral-400">•</span>
                    <span>{req}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-2 pt-2">
            <button
              onClick={handleScreen}
              disabled={screening}
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
            >
              {screening ? "Re-screening..." : "Re-screen"}
            </button>
            {job.is_active && job.role_match && (job.match_score ?? 0) >= 60 && (
              <button
                onClick={handleApply}
                disabled={applying}
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {applying ? "Starting application..." : "Apply"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: "emerald" | "rose" }) {
  const valueColor =
    color === "emerald" ? "text-emerald-700" : color === "rose" ? "text-rose-700" : "text-neutral-900";
  return (
    <div className="rounded-md border border-neutral-200 bg-white px-3 py-2">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={`text-sm font-medium ${valueColor}`}>{value}</p>
    </div>
  );
}
