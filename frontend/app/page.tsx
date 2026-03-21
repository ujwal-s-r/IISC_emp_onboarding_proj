"use client";

import { useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { EmployerFormPanel } from "@/components/home/EmployerFormPanel";
import { ResumePanel } from "@/components/home/ResumePanel";
import { EventTree } from "@/components/home/EventTree";
import { HistoryDropdown } from "@/components/home/HistoryDropdown";
import { JourneyTrackGraphs } from "@/components/home/JourneyTrackGraphs";
import { useEmployerPipeline } from "@/hooks/useEmployerPipeline";
import { useEmployeePipeline } from "@/hooks/useEmployeePipeline";
import { API_BASE } from "@/lib/config";

export default function HomePage() {
  const {
    events,
    streams,
    streamKey,
    roleId,
    wsStatus,
    submitError,
    submitState,
    pipelineDone,
    historicalData,
    historicalLoading,
    historicalMode,
    resetVersion,
    layoutFocus,
    setLayoutFocus,
    startAnalysis,
    loadRoleById,
    resetAll,
  } = useEmployerPipeline();

  const {
    events: employeeEvents,
    streams: employeeStreams,
    streamKey: employeeStreamKey,
    wsStatus: employeeWsStatus,
    pipelineDone: employeePipelineDone,
    employeeBusy,
    connect: connectEmployeeStream,
    orchestrationScrollRef: employeeOrchestrationScrollRef,
  } = useEmployeePipeline(roleId, setLayoutFocus);

  const busy = wsStatus === "connecting" || wsStatus === "open";
  const wsOpen = wsStatus === "open";
  const employerOrchestrationRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const { leftPane, rightPane } = useMemo(() => {
    const base =
      "glass-pane-split flex min-h-0 min-w-0 flex-col p-4 sm:p-5 md:min-h-[calc(100vh-10.5rem)]";

    const leftFlex =
      layoutFocus === "employer"
        ? "md:flex-[1.72]"
        : layoutFocus === "resume"
          ? "md:flex-[0.78]"
          : "md:flex-1";

    const rightFlex =
      layoutFocus === "resume"
        ? "md:flex-[1.72]"
        : layoutFocus === "employer"
          ? "md:flex-[0.78]"
          : "md:flex-1";

    const leftStyle =
      layoutFocus === "employer"
        ? "glass-pane-split--focus"
        : layoutFocus === "resume"
          ? "glass-pane-split--dim"
          : "";

    const rightStyle =
      layoutFocus === "resume"
        ? "glass-pane-split--focus"
        : layoutFocus === "employer"
          ? "glass-pane-split--dim"
          : "";

    return {
      leftPane: `${base} ${leftFlex} ${leftStyle}`.trim(),
      rightPane: `${base} ${rightFlex} ${rightStyle}`.trim(),
    };
  }, [layoutFocus]);

  const journeyData = useMemo(() => {
    for (let i = employeeEvents.length - 1; i >= 0; i--) {
      const ev = employeeEvents[i];
      if (ev.phase === "journey" && ev.type === "result" && ev.step === "journey_ready") {
        return ev.data;
      }
    }
    return null;
  }, [employeeEvents]);

  return (
    <div className="relative z-10 mx-auto max-w-[1920px] px-3 py-6 sm:px-5 lg:px-8 lg:py-8">
      <header className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="max-w-4xl">
            <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Role intelligence
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-white/50 sm:text-base">
              <span className="text-white/65">Split workspace</span> — employer (JD, team
              context, live phases) on the left; resume track on the right. From tablet size
              up, both columns stay side by side; focus shifts automatically while the pipeline
              runs, and you can override anytime.
            </p>
            <p className="mt-2 font-mono text-[11px] text-white/35">API: {API_BASE}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              resetAll();
              router.replace("/");
            }}
            className="rounded-xl border border-white/20 bg-white/[0.08] px-4 py-2 text-sm font-medium text-white transition hover:bg-white/15"
          >
            + New Analysis
          </button>
        </div>
      </header>

      <div className="glass-toolbar mb-5">
        <span className="px-1 text-[11px] font-medium uppercase tracking-wider text-white/40">
          Focus
        </span>
        {(["balanced", "employer", "resume"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setLayoutFocus(m)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              layoutFocus === m
                ? "bg-white text-black shadow-md shadow-black/20"
                : "text-white/65 hover:bg-white/10 hover:text-white"
            }`}
          >
            {m === "balanced" ? "Balanced" : m === "employer" ? "Role setup" : "Resume"}
          </button>
        ))}
        <HistoryDropdown
          currentRoleId={roleId}
          onSelect={(id) => {
            router.replace(`/?role=${encodeURIComponent(id)}`);
            void loadRoleById(id);
          }}
          disabled={busy || historicalLoading}
        />
        <span className="ml-auto font-mono text-[11px] text-white/40">
          Role WS: {wsStatus}
          {busy ? " · pipeline" : ""}
          {pipelineDone ? " · done" : ""}
          {" · "}
          Resume WS: {employeeWsStatus}
          {employeeBusy ? " · pipeline" : ""}
          {employeePipelineDone ? " · done" : ""}
        </span>
      </div>

      {/* Side-by-side from md (768px+); stacked on phones */}
      <div className="flex flex-col gap-4 md:flex-row md:items-stretch md:gap-4">
        {/* Left: employer + live stream */}
        <section
          className={leftPane}
          aria-label="Employer setup and live orchestration"
          onPointerDown={() => setLayoutFocus("employer")}
        >
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-medium text-white/95">Employer</h2>
                {layoutFocus === "employer" && busy ? (
                  <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300/95">
                    Primary
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-xs text-white/45">
                <code className="text-white/55">POST /api/v1/employer/setup-role</code>
              </p>
              {submitState === "submitting" ? (
                <p className="mt-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
                  Calling backend: POST <code>/api/v1/employer/setup-role</code> ...
                </p>
              ) : null}
              {submitState === "streaming" ? (
                <p className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                  Connected. Streaming live phases and steps from backend events.
                </p>
              ) : null}
              {historicalMode && historicalData ? (
                <p className="mt-2 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs text-white/70">
                  Loaded historical role <code>{historicalData.id}</code>. You can review the
                  saved orchestration and still run a new analysis.
                </p>
              ) : null}
              <div className="mt-4">
                <EmployerFormPanel
                  onSubmit={startAnalysis}
                  disabled={busy}
                  error={submitError}
                  formKey={`${resetVersion}:${roleId ?? "new"}`}
                  initialValues={
                    historicalData
                      ? {
                          title: historicalData.title,
                          seniority: historicalData.seniority,
                          jdText: historicalData.jd_text ?? "",
                          teamContextText: historicalData.team_context_text ?? "",
                        }
                      : null
                  }
                />
              </div>
            </div>

            <div className="mt-6 flex min-h-0 flex-1 flex-col border-t border-white/10 pt-5">
              <div className="mb-3 shrink-0">
                <h3 className="text-sm font-semibold text-white/90">Live orchestration</h3>
                <p className="mt-0.5 text-[11px] text-white/40">
                  Redis → <code className="text-white/50">/ws/employer/setup/{"{role_id}"}</code>
                </p>
              </div>
              <div
                ref={employerOrchestrationRef}
                className="min-h-[200px] flex-1 overflow-y-auto overflow-x-hidden pr-1 [scrollbar-gutter:stable] md:min-h-[280px]"
              >
                <EventTree
                  events={events}
                  streams={streams}
                  streamKey={streamKey}
                  wsOpen={wsOpen}
                  wsStatus={wsStatus}
                  scrollParentRef={employerOrchestrationRef}
                />
              </div>
            </div>
          </div>
        </section>

        {/* Right: resume only */}
        <section className={rightPane} aria-label="Employee resume">
          <ResumePanel
            key={`resume:${resetVersion}:${roleId ?? "new"}`}
            roleId={roleId}
            compact={layoutFocus === "employer" && busy}
            emphasized={layoutFocus === "resume"}
            onUserActivate={() => setLayoutFocus("resume")}
            onEmployeeSessionStart={connectEmployeeStream}
            employeeEvents={employeeEvents}
            employeeStreams={employeeStreams}
            employeeStreamKey={employeeStreamKey}
            employeeWsOpen={employeeWsStatus === "open"}
            employeeWsStatus={employeeWsStatus}
            employeePipelineDone={employeePipelineDone}
            employeeBusy={employeeBusy}
            employeeOrchestrationRef={employeeOrchestrationScrollRef}
          />
        </section>
      </div>

      {journeyData ? <JourneyTrackGraphs journeyData={journeyData} /> : null}

      <p className="mt-6 text-center text-[11px] text-white/30 md:hidden">
        Tip: rotate to landscape or widen the window for the full split layout.
      </p>
    </div>
  );
}
