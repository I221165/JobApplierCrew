"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export function Nav() {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const notifs = await api.listNotifications(true);
        if (!cancelled) setUnread(notifs.length);
      } catch {
        // backend might not be up — fail silently
      }
    }
    poll();
    const id = setInterval(poll, 30_000);     // re-check every 30s
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <nav className="mx-auto max-w-5xl flex items-center gap-6 px-6 py-4">
      <Link href="/" className="font-semibold text-lg">
        Job Applier
      </Link>
      <Link href="/" className="text-sm text-neutral-600 hover:text-neutral-900">
        Search
      </Link>
      <Link href="/searches" className="text-sm text-neutral-600 hover:text-neutral-900">
        Saved
      </Link>
      <Link href="/notifications" className="relative text-sm text-neutral-600 hover:text-neutral-900">
        Notifications
        {unread > 0 && (
          <span className="absolute -top-2 -right-5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-medium text-white">
            {unread}
          </span>
        )}
      </Link>
      <Link href="/cv" className="text-sm text-neutral-600 hover:text-neutral-900">
        CV
      </Link>
    </nav>
  );
}
