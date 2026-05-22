import Link from "next/link";
import type { Job } from "@/lib/types";
import { ScoreBadge } from "./ScoreBadge";

export function JobCard({ job }: { job: Job }) {
  return (
    <Link
      href={`/jobs/${job.id}`}
      className="block rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-300 hover:shadow-sm transition"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-medium text-neutral-900 leading-tight">{job.title}</h3>
        <ScoreBadge score={job.match_score} />
      </div>
      {job.actual_title && job.actual_title !== job.title && (
        <p className="mt-1 text-xs text-neutral-500">Actual title: {job.actual_title}</p>
      )}
      <p className="mt-2 text-sm text-neutral-600 line-clamp-2">{job.snippet}</p>
      <div className="mt-3 flex items-center gap-2 text-xs text-neutral-500">
        <span className="truncate">{new URL(job.url).hostname}</span>
        {job.role_match === false && (
          <span className="text-rose-600">• role mismatch</span>
        )}
        {job.is_active === false && (
          <span className="text-amber-600">• closed</span>
        )}
      </div>
    </Link>
  );
}
