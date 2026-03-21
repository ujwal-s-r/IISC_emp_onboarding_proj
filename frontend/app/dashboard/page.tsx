import Link from "next/link";
import { API_BASE } from "@/lib/config";

async function fetchRoles() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/employer/roles`, {
      next: { revalidate: 0 },
    });
    if (!res.ok) return { error: await res.text(), roles: [] as unknown[] };
    const roles = await res.json();
    return { error: null, roles: Array.isArray(roles) ? roles : [] };
  } catch (e) {
    return {
      error: e instanceof Error ? e.message : "Fetch failed",
      roles: [] as unknown[],
    };
  }
}

export default async function DashboardPage() {
  const { error, roles } = await fetchRoles();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-white/45">
            Roles from <code className="text-white/55">GET /api/v1/employer/roles</code>
          </p>
        </div>
        <Link
          href="/"
          className="rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2 text-sm text-white/80 transition hover:bg-white/10"
        >
          ← Home
        </Link>
      </div>

      {error ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          Could not load roles ({error}). Is the API running at {API_BASE}?
        </div>
      ) : null}

      <ul className="mt-6 space-y-3">
        {roles.length === 0 && !error ? (
          <li className="glass-panel p-6 text-center text-sm text-white/45">
            No roles yet. Create one from the home page.
          </li>
        ) : null}
        {roles.map((item) => {
          const r = item as Record<string, unknown>;
          return (
          <li key={String(r.id)} className="glass-panel flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <p className="font-medium text-white/90">{String(r.title ?? "")}</p>
              <p className="mt-0.5 font-mono text-xs text-white/40">{String(r.id ?? "")}</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-white/50">
              <span className="rounded-full border border-white/10 px-2 py-1">
                {String(r.status ?? "")}
              </span>
              <span>{String(r.seniority ?? "")}</span>
            </div>
          </li>
        );
        })}
      </ul>
    </div>
  );
}
