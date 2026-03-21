"use client";

import { useId, useState, type ReactNode } from "react";

export function Collapsible({
  title,
  subtitle,
  defaultOpen = true,
  badge,
  children,
  className = "",
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  defaultOpen?: boolean;
  badge?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();

  return (
    <div
      className={`rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur-md ${className}`}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition hover:bg-white/[0.04]"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-block h-2 w-2 shrink-0 rounded-full transition ${
                open ? "bg-white" : "bg-white/40"
              }`}
            />
            <span className="font-medium text-white/95">{title}</span>
            {badge}
          </div>
          {subtitle ? (
            <div className="mt-1 text-xs text-white/50">{subtitle}</div>
          ) : null}
        </div>
        <span className="shrink-0 text-white/40">{open ? "−" : "+"}</span>
      </button>
      {open ? (
        <div id={id} className="border-t border-white/10 px-4 py-3">
          {children}
        </div>
      ) : null}
    </div>
  );
}
