"use client";

import { useState, type FormEvent, type RefObject } from "react";
import { employeeOnboardUrl } from "@/lib/config";
import { EmployeeEventTree } from "@/components/home/EmployeeEventTree";
import type { NormalizedEmployeeEvent } from "@/lib/employeeTypes";
import type { StreamBuffers } from "@/hooks/useEmployerPipeline";

export function ResumePanel({
  roleId,
  compact,
  emphasized,
  disabled,
  onUserActivate,
  onEmployeeSessionStart,
  employeeEvents,
  employeeStreams,
  employeeStreamKey,
  employeeWsOpen,
  employeeWsStatus,
  employeePipelineDone,
  employeeBusy,
  employeeOrchestrationRef,
}: {
  roleId: string | null;
  compact?: boolean;
  emphasized?: boolean;
  disabled?: boolean;
  onUserActivate?: () => void;
  onEmployeeSessionStart: (employeeId: string) => void;
  employeeEvents: NormalizedEmployeeEvent[];
  employeeStreams: Record<string, StreamBuffers>;
  employeeStreamKey: (phase: string, step: string) => string;
  employeeWsOpen: boolean;
  employeeWsStatus: "idle" | "connecting" | "open" | "closed" | "error";
  employeePipelineDone: boolean;
  employeeBusy: boolean;
  employeeOrchestrationRef: RefObject<HTMLDivElement | null>;
}) {
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErr(null);
    setMsg(null);
    if (!roleId) {
      setErr("Create a role first (start analysis on the left).");
      return;
    }
    const fd = new FormData(e.currentTarget);
    const file = fd.get("resume_file");
    if (!(file instanceof File) || file.size === 0) {
      setErr("Choose a resume PDF (or file).");
      return;
    }
    fd.set("role_id", roleId);
    setLoading(true);
    try {
      const res = await fetch(employeeOnboardUrl(), { method: "POST", body: fd });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const body = (await res.json()) as { id: string };
      if (!body.id) throw new Error("No employee id returned");
      setMsg(`Session ${body.id.slice(0, 8)}… — streaming pipeline.`);
      onEmployeeSessionStart(body.id);
      e.currentTarget.reset();
    } catch (er) {
      setErr(er instanceof Error ? er.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const formLocked = !roleId || disabled || loading || employeeBusy;

  return (
    <div
      role="region"
      tabIndex={-1}
      onPointerDown={() => onUserActivate?.()}
      onFocusCapture={() => onUserActivate?.()}
      className={`flex h-full min-h-[220px] flex-col rounded-xl border border-white/10 bg-white/[0.04] p-5 shadow-inner shadow-black/20 backdrop-blur-xl transition-all duration-500 md:min-h-0 ${
        compact ? "md:scale-[0.985]" : ""
      } ${
        emphasized
          ? "border-white/20 ring-1 ring-white/20 ring-offset-2 ring-offset-transparent"
          : ""
      } `}
    >
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/45">
            Employee resume
          </p>
          <p className="mt-1 text-sm text-white/50">
            PDF upload for the right-hand track. Requires an active{" "}
            <span className="text-white/70">role id</span> from the left.
          </p>
          {roleId ? (
            <p className="mt-2 font-mono text-[11px] text-emerald-300/90">
              Role: {roleId}
            </p>
          ) : (
            <p className="mt-2 text-xs text-amber-200/80">
              Waiting for role id after you start analysis…
            </p>
          )}
        </div>

        <div className="mt-4 shrink-0">
          <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-white/60">Resume file</span>
              <input
                name="resume_file"
                type="file"
                accept=".pdf,application/pdf"
                disabled={formLocked}
                className="text-xs text-white/60 file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-white/80"
              />
            </label>
            <button
              type="submit"
              disabled={formLocked}
              className="rounded-xl border border-white/20 bg-white/[0.08] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Uploading…" : "Start resume analysis"}
            </button>
          </form>

          {loading ? (
            <p className="mt-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
              Calling backend: POST <code className="text-sky-100/90">/api/v1/employee/onboard-path</code> …
            </p>
          ) : null}
          {employeeWsOpen || employeeWsStatus === "connecting" ? (
            <p className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              Connected. Streaming resume pipeline phases from backend events.
            </p>
          ) : null}
          {employeePipelineDone ? (
            <p className="mt-2 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs text-white/60">
              Resume pipeline finished (persist complete).
            </p>
          ) : null}

          {err ? (
            <p className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {err}
            </p>
          ) : null}
          {msg && !err ? (
            <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
              {msg}
            </p>
          ) : null}
        </div>

        <div className="mt-6 flex min-h-0 flex-1 flex-col border-t border-white/10 pt-5">
          <div className="mb-3 shrink-0">
            <h3 className="text-sm font-semibold text-white/90">Live orchestration</h3>
            <p className="mt-0.5 text-[11px] text-white/40">
              Redis →{" "}
              <code className="text-white/50">/ws/employee/setup/{"{employee_id}"}</code>
            </p>
          </div>
          <div
            ref={employeeOrchestrationRef}
            className="min-h-[200px] flex-1 overflow-y-auto overflow-x-hidden pr-1 [scrollbar-gutter:stable] md:min-h-[280px]"
          >
            <EmployeeEventTree
              events={employeeEvents}
              streams={employeeStreams}
              streamKey={employeeStreamKey}
              wsOpen={employeeWsOpen}
              wsStatus={employeeWsStatus}
              scrollParentRef={employeeOrchestrationRef}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
