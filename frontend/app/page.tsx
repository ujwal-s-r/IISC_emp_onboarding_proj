"use client";

import { useMemo } from "react";
import { EmployerFormPanel } from "@/components/home/EmployerFormPanel";
import { ResumePanel } from "@/components/home/ResumePanel";
import { EventTree } from "@/components/home/EventTree";
import { useEmployerPipeline } from "@/hooks/useEmployerPipeline";
import { API_BASE } from "@/lib/config";

export default function HomePage() {
  const {
    events,
    streams,
    streamKey,
    roleId,
    wsStatus,
    submitError,
    pipelineDone,
    layoutFocus,
    setLayoutFocus,
    startAnalysis,
  } = useEmployerPipeline();

  const busy = wsStatus === "connecting" || wsStatus === "open";
  const wsOpen = wsStatus === "open";

  const gridClass = useMemo(() => {
    if (layoutFocus === "employer") {
      return "lg:grid-cols-[minmax(0,1.85fr)_minmax(0,1fr)]";
    }
    if (layoutFocus === "resume") {
      return "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.85fr)]";
    }
    return "lg:grid-cols-2";
  }, [layoutFocus]);

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6 lg:py-10">
      <header className="mb-8 max-w-3xl">
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Role intelligence
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-white/50 sm:text-base">
          Split workspace: employer inputs on the left (JD + team context + metadata),
          employee resume on the right. Start analysis to open a live WebSocket and walk
          through all orchestration phases exactly as emitted by the API.
        </p>
        <p className="mt-2 font-mono text-[11px] text-white/35">
          API: {API_BASE}
        </p>
      </header>

      <div
        className={`mb-6 flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-2 backdrop-blur-md`}
      >
        <span className="px-2 text-xs text-white/40">Focus</span>
        {(["balanced", "employer", "resume"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setLayoutFocus(m)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              layoutFocus === m
                ? "bg-white text-black"
                : "text-white/60 hover:bg-white/10 hover:text-white"
            }`}
          >
            {m === "balanced" ? "Balanced" : m === "employer" ? "Role setup" : "Resume"}
          </button>
        ))}
        <span className="ml-auto text-xs text-white/35">
          WS: {wsStatus}
          {pipelineDone ? " · pipeline complete" : ""}
        </span>
      </div>

      <div className={`grid grid-cols-1 gap-6 transition-[grid-template-columns] duration-500 ${gridClass}`}>
        <section
          className={`glass-panel flex flex-col p-5 sm:p-6 ${
            layoutFocus === "resume" ? "lg:opacity-90" : ""
          }`}
        >
          <h2 className="text-lg font-medium text-white/90">Employer</h2>
          <p className="mt-1 text-xs text-white/45">
            Matches <code className="text-white/55">POST /api/v1/employer/setup-role</code>{" "}
            (multipart).
          </p>
          <div className="mt-5">
            <EmployerFormPanel
              onSubmit={startAnalysis}
              disabled={busy}
              error={submitError}
            />
          </div>
        </section>

        <section
          className={`min-h-[200px] transition-transform duration-500 ${
            layoutFocus === "employer" ? "lg:scale-[0.97] lg:opacity-90" : ""
          }`}
        >
          <ResumePanel roleId={roleId} compact={layoutFocus === "employer"} />
        </section>
      </div>

      <section className="mt-10 glass-panel p-5 sm:p-6">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-medium text-white/90">Live orchestration</h2>
            <p className="mt-1 text-xs text-white/45">
              Redis-backed events via <code className="text-white/55">/ws/employer/setup/{"{role_id}"}</code>
            </p>
          </div>
        </div>
        <EventTree
          events={events}
          streams={streams}
          streamKey={streamKey}
          wsOpen={wsOpen}
        />
      </section>
    </div>
  );
}
