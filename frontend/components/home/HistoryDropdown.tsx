"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { API_BASE } from "@/lib/config";

interface RoleOption {
  id: string;
  title: string;
  seniority?: string;
  status?: string;
}

export function HistoryDropdown({
  currentRoleId,
  onSelect,
  disabled,
}: {
  currentRoleId: string | null;
  onSelect: (roleId: string) => void;
  disabled?: boolean;
}) {
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!open) return;

    async function run() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/v1/employer/roles`);
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(txt || res.statusText);
        }
        const payload = (await res.json()) as unknown;
        const list = Array.isArray(payload)
          ? payload
          : payload && typeof payload === "object" && Array.isArray((payload as { roles?: unknown[] }).roles)
            ? (payload as { roles: unknown[] }).roles
            : [];

        if (!cancelled) {
          const normalized = list
            .map((r) => r as Record<string, unknown>)
            .filter((r) => typeof r.id === "string")
            .map((r) => ({
              id: String(r.id),
              title: String(r.title ?? "Untitled role"),
              seniority: r.seniority ? String(r.seniority) : undefined,
              status: r.status ? String(r.status) : undefined,
            }));
          setRoles(normalized);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load role history");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const sorted = useMemo(
    () =>
      [...roles].sort((a, b) => {
        if (a.id === currentRoleId) return -1;
        if (b.id === currentRoleId) return 1;
        return 0;
      }),
    [roles, currentRoleId]
  );

  return (
    <>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(true)}
        className="ml-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-white/80 transition hover:border-white/20 hover:bg-white/10 disabled:opacity-50"
      >
        History
      </button>

      {mounted
        ? createPortal(
            <div
              className={`fixed inset-0 z-[120] flex items-center justify-center p-4 transition-all duration-300 ${
                open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
              }`}
              aria-hidden={!open}
            >
              <button
                type="button"
                aria-label="Close history modal"
                onClick={() => setOpen(false)}
                className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
              />
              <div
                role="dialog"
                aria-modal="true"
                aria-label="History"
                className={`relative w-full max-w-2xl rounded-2xl border border-white/15 bg-zinc-950/85 p-4 shadow-2xl shadow-black/60 backdrop-blur-xl transition-all duration-300 sm:p-5 ${
                  open ? "translate-y-0 scale-100 opacity-100" : "translate-y-4 scale-95 opacity-0"
                }`}
              >
                <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white/95">Role History</h3>
                    <p className="mt-1 text-xs text-white/45">
                      Select a previous role to rehydrate the full workspace.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="rounded-lg border border-white/10 px-2.5 py-1 text-xs text-white/70 transition hover:bg-white/10 hover:text-white"
                  >
                    Close
                  </button>
                </div>

                {loading ? (
                  <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
                    Loading role history...
                  </div>
                ) : null}

                {error ? (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                    Could not fetch history ({error}).
                  </div>
                ) : null}

                {!loading && !error ? (
                  <div className="max-h-[58vh] space-y-2 overflow-y-auto pr-1">
                    {!sorted.length ? (
                      <div className="rounded-xl border border-dashed border-white/15 bg-white/[0.03] p-6 text-center text-sm text-white/45">
                        No past roles found.
                      </div>
                    ) : (
                      sorted.map((r) => {
                        const active = r.id === currentRoleId;
                        return (
                          <button
                            key={r.id}
                            type="button"
                            onClick={() => {
                              onSelect(r.id);
                              setOpen(false);
                            }}
                            className={`w-full rounded-xl border px-3 py-2.5 text-left transition ${
                              active
                                ? "border-emerald-400/35 bg-emerald-500/10"
                                : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]"
                            }`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <p className="truncate text-sm font-medium text-white/90">{r.title}</p>
                              <span className="shrink-0 rounded-full border border-white/15 px-2 py-0.5 text-[10px] uppercase text-white/55">
                                {r.seniority ?? "-"}
                              </span>
                            </div>
                            <p className="mt-1 font-mono text-[11px] text-white/45">{r.id}</p>
                            {r.status ? (
                              <p className="mt-1 text-[11px] text-white/50">Status: {r.status}</p>
                            ) : null}
                          </button>
                        );
                      })
                    )}
                  </div>
                ) : null}
              </div>
            </div>,
            document.body
          )
        : null}
    </>
  );
}
