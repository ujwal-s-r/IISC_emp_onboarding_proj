"use client";

import { useState, type FormEvent } from "react";
import { employeeOnboardUrl } from "@/lib/config";

export function ResumePanel({
  roleId,
  compact,
  disabled,
}: {
  roleId: string | null;
  compact?: boolean;
  disabled?: boolean;
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
      setMsg(`Employee session ${body.id} created. Onboarding pipeline will run when wired.`);
      e.currentTarget.reset();
    } catch (er) {
      setErr(er instanceof Error ? er.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className={`flex flex-col rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-md transition-all ${
        compact ? "lg:scale-[0.98] lg:opacity-90" : ""
      }`}
    >
      <p className="text-xs font-semibold uppercase tracking-wider text-white/45">
        Employee resume
      </p>
      <p className="mt-1 text-sm text-white/50">
        PDF upload for the right-hand onboarding track. Requires an active{" "}
        <span className="text-white/70">role id</span> from the left.
      </p>
      {roleId ? (
        <p className="mt-2 font-mono text-[11px] text-emerald-300/90">Role: {roleId}</p>
      ) : (
        <p className="mt-2 text-xs text-amber-200/80">
          Waiting for role id after you start analysis…
        </p>
      )}

      <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3">
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="text-white/60">Resume file</span>
          <input
            name="resume_file"
            type="file"
            accept=".pdf,application/pdf"
            disabled={!roleId || disabled || loading}
            className="text-xs text-white/60 file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-white/80"
          />
        </label>
        <button
          type="submit"
          disabled={!roleId || disabled || loading}
          className="rounded-xl border border-white/20 bg-white/[0.08] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Uploading…" : "Submit resume"}
        </button>
      </form>

      {err ? (
        <p className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
          {err}
        </p>
      ) : null}
      {msg ? (
        <p className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
          {msg}
        </p>
      ) : null}
    </div>
  );
}
