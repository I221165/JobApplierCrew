"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { NotificationWithJob } from "@/lib/types";
import { ScoreBadge } from "../components/ScoreBadge";

export default function NotificationsPage() {
  const [notifs, setNotifs] = useState<NotificationWithJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setNotifs(await api.listNotifications(unreadOnly));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unreadOnly]);

  async function handleMarkRead(id: string) {
    await api.markNotificationRead(id);
    setNotifs((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Notifications</h1>
          <p className="mt-1 text-sm text-neutral-600">
            New high-match jobs from your{" "}
            <Link href="/searches" className="underline">saved searches</Link>.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="rounded border-neutral-300"
          />
          Unread only
        </label>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-neutral-500">Loading...</p>
      ) : notifs.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          No notifications yet.{" "}
          <Link href="/searches" className="underline">Add a saved search</Link> to start receiving them.
        </div>
      ) : (
        <div className="grid gap-3">
          {notifs.map((n) => (
            <div
              key={n.id}
              className={`rounded-lg border bg-white p-4 ${n.read ? "border-neutral-200" : "border-sky-300 bg-sky-50/30"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {!n.read && <span className="h-2 w-2 rounded-full bg-sky-500" />}
                    <p className="font-medium truncate">{n.job?.title ?? "Job removed"}</p>
                  </div>
                  <p className="mt-1 text-xs text-neutral-500">
                    {new Date(n.created_at).toLocaleString()}
                    {n.job?.url && (
                      <>
                        {" · "}
                        <span>{new URL(n.job.url).hostname}</span>
                      </>
                    )}
                  </p>
                </div>
                <ScoreBadge score={n.match_score} />
              </div>
              <div className="mt-3 flex gap-2">
                {n.job && (
                  <Link
                    href={`/jobs/${n.job.id}`}
                    onClick={() => !n.read && handleMarkRead(n.id)}
                    className="rounded-md bg-neutral-900 px-3 py-1 text-xs font-medium text-white hover:bg-neutral-800"
                  >
                    View job
                  </Link>
                )}
                {!n.read && (
                  <button
                    onClick={() => handleMarkRead(n.id)}
                    className="rounded-md border border-neutral-300 px-3 py-1 text-xs font-medium hover:bg-neutral-50"
                  >
                    Mark read
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
