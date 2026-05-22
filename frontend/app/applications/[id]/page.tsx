"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/lib/types";

const PHASES: { key: ApplicationStatus; label: string }[] = [
  { key: "queued", label: "Queued" },
  { key: "gap_analysis", label: "Gap analysis" },
  { key: "cover_letter", label: "Tailoring CV & cover letter" },
  { key: "latex", label: "Generating LaTeX PDF" },
  { key: "done", label: "Done" },
];

function phaseIndex(status: ApplicationStatus): number {
  const idx = PHASES.findIndex((p) => p.key === status);
  return idx >= 0 ? idx : 0;
}

export default function ApplicationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [app, setApp] = useState<Application | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initial fetch
  useEffect(() => {
    api.getApplication(id).then(setApp).catch((e) => setError(String(e)));
  }, [id]);

  // SSE stream
  useEffect(() => {
    const es = new EventSource(api.streamApplicationUrl(id));
    es.addEventListener("update", () => {
      // Re-fetch full application on each update — the stream sends partials
      api.getApplication(id).then(setApp).catch(() => {});
    });
    es.addEventListener("complete", () => {
      api.getApplication(id).then(setApp).catch(() => {});
      es.close();
    });
    es.onerror = () => {
      // EventSource auto-retries; just log
      console.error("SSE error");
    };
    return () => es.close();
  }, [id]);

  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</div>
    );
  }
  if (!app) return <p className="text-sm text-neutral-500">Loading...</p>;

  const idx = phaseIndex(app.status);
  const isFailed = app.status === "failed";
  const isDone = app.status === "done";

  return (
    <div className="space-y-6">
      <Link href={`/jobs/${app.job_id}`} className="text-sm text-neutral-600 hover:text-neutral-900">
        ← Back to job
      </Link>

      <div>
        <h1 className="text-2xl font-semibold">Application in progress</h1>
        <p className="mt-1 text-sm text-neutral-600">{app.progress_message || "Starting..."}</p>
      </div>

      <ol className="space-y-2">
        {PHASES.map((p, i) => {
          const state = isFailed
            ? i < idx
              ? "done"
              : i === idx
              ? "failed"
              : "pending"
            : i < idx
            ? "done"
            : i === idx
            ? "active"
            : "pending";
          const dotColor =
            state === "done"
              ? "bg-emerald-500"
              : state === "active"
              ? "bg-sky-500 animate-pulse"
              : state === "failed"
              ? "bg-rose-500"
              : "bg-neutral-300";
          const textColor = state === "pending" ? "text-neutral-400" : "text-neutral-900";
          return (
            <li key={p.key} className="flex items-center gap-3">
              <span className={`h-2.5 w-2.5 rounded-full ${dotColor}`} />
              <span className={`text-sm ${textColor}`}>{p.label}</span>
            </li>
          );
        })}
      </ol>

      {isFailed && app.error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
          <p className="font-medium mb-1">Failed</p>
          <pre className="whitespace-pre-wrap text-xs">{app.error}</pre>
        </div>
      )}

      {isDone && (
        <div className="space-y-4">
          {app.pdf_path && (
            <a
              href={api.pdfUrl(app.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            >
              Download tailored CV (PDF)
            </a>
          )}

          {app.cover_subject && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4">
              <h3 className="text-sm font-medium text-neutral-700 mb-2">Email subject</h3>
              <p className="text-sm">{app.cover_subject}</p>
            </section>
          )}

          {app.cover_body && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4">
              <h3 className="text-sm font-medium text-neutral-700 mb-2">Cover letter</h3>
              <pre className="whitespace-pre-wrap text-sm font-sans">{app.cover_body}</pre>
            </section>
          )}

          {app.tailored_cv && (
            <section className="rounded-lg border border-neutral-200 bg-white p-4">
              <h3 className="text-sm font-medium text-neutral-700 mb-2">Tailored CV (text)</h3>
              <pre className="whitespace-pre-wrap text-xs font-mono max-h-96 overflow-y-auto">{app.tailored_cv}</pre>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
