"use client";

import { useRef, type FormEvent } from "react";

const SENIORITY = ["intern", "junior", "mid", "senior", "lead"] as const;

export function EmployerFormPanel({
  onSubmit,
  disabled,
  error,
  initialValues,
  formKey,
}: {
  onSubmit: (fd: FormData) => void | Promise<void>;
  disabled?: boolean;
  error?: string | null;
  initialValues?: {
    title?: string;
    seniority?: string;
    jdText?: string;
    teamContextText?: string;
  } | null;
  formKey?: string;
}) {
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!formRef.current || disabled) return;
    const fd = new FormData(formRef.current);
    await onSubmit(fd);
  }

  return (
    <form
      key={formKey}
      ref={formRef}
      onSubmit={handleSubmit}
      className="flex flex-col gap-5"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="text-white/70">
            Title <span className="text-rose-400">*</span>
          </span>
          <input
            name="title"
            required
            placeholder="e.g. Senior Data Engineer"
            defaultValue={initialValues?.title ?? ""}
            disabled={disabled}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-white placeholder:text-white/25 outline-none ring-white/20 transition focus:ring-2 disabled:opacity-50"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm">
          <span className="text-white/70">
            Seniority <span className="text-rose-400">*</span>
          </span>
          <select
            name="seniority"
            required
            defaultValue={initialValues?.seniority ?? "senior"}
            disabled={disabled}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-white outline-none ring-white/20 transition focus:ring-2 disabled:opacity-50"
          >
            {SENIORITY.map((s) => (
              <option key={s} value={s} className="bg-zinc-900">
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-md">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/45">
            Job description
          </p>
          <p className="mt-1 text-xs text-white/35">
            Upload a file or paste text (at least one).
          </p>
          <label className="mt-3 flex flex-col gap-1.5 text-sm">
            <span className="text-white/60">JD file</span>
            <input
              name="jd_file"
              type="file"
              accept=".pdf,.txt,.doc,.docx,application/pdf,text/plain"
              disabled={disabled}
              className="text-xs text-white/60 file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-white/80"
            />
          </label>
          <label className="mt-3 flex flex-col gap-1.5 text-sm">
            <span className="text-white/60">JD text</span>
            <textarea
              name="jd_text"
              rows={5}
              placeholder="Paste JD here if not uploading a file…"
              defaultValue={initialValues?.jdText ?? ""}
              disabled={disabled}
              className="resize-y rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/25 outline-none ring-white/20 focus:ring-2 disabled:opacity-50"
            />
          </label>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 backdrop-blur-md">
          <p className="text-xs font-semibold uppercase tracking-wider text-white/45">
            Team context
          </p>
          <p className="mt-1 text-xs text-white/35">
            Upload a file or paste text (at least one).
          </p>
          <label className="mt-3 flex flex-col gap-1.5 text-sm">
            <span className="text-white/60">Team context file</span>
            <input
              name="team_context_file"
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              disabled={disabled}
              className="text-xs text-white/60 file:mr-3 file:rounded-lg file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-white/80"
            />
          </label>
          <label className="mt-3 flex flex-col gap-1.5 text-sm">
            <span className="text-white/60">Team context text</span>
            <textarea
              name="team_context_text"
              rows={5}
              placeholder="Paste team context here if not uploading a file…"
              defaultValue={initialValues?.teamContextText ?? ""}
              disabled={disabled}
              className="resize-y rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm text-white placeholder:text-white/25 outline-none ring-white/20 focus:ring-2 disabled:opacity-50"
            />
          </label>
        </div>
      </div>

      {error ? (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={disabled}
        className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-white/10 transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {disabled ? "Analysis running…" : "Start analysis"}
      </button>
    </form>
  );
}
