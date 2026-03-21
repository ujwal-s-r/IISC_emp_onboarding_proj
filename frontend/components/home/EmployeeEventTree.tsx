"use client";

import {
  useLayoutEffect,
  useMemo,
  useRef,
  type RefObject,
} from "react";
import {
  EMPLOYEE_PHASE_LABEL,
  EMPLOYEE_PHASE_ORDER,
  type EmployeePhase,
  type NormalizedEmployeeEvent,
  isEmployeePhase,
} from "@/lib/employeeTypes";
import { Collapsible } from "@/components/Collapsible";
import type { StreamBuffers } from "@/hooks/useEmployerPipeline";

interface ResumeSkill {
  skill_name: string;
  context_depth?: string;
}

function LogRow({ ev }: { ev: NormalizedEmployeeEvent }) {
  return (
    <div
      data-orch-step={ev.id}
      className="rounded-lg border border-white/5 bg-black/20 px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-2 text-white/80">
        <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-white/60">
          {ev.type}
        </span>
        <span className="font-mono text-xs text-white/50">{ev.step}</span>
      </div>
      {ev.message ? (
        <p className="mt-1 text-white/70">{ev.message}</p>
      ) : null}
      {ev.model ? (
        <p className="mt-1 text-xs text-white/40">Model: {ev.model}</p>
      ) : null}
      <PayloadPreview data={ev.data} />
    </div>
  );
}

function PayloadPreview({ data }: { data: Record<string, unknown> }) {
  const keys = Object.keys(data);
  if (!keys.length) return null;
  if (data.resume_preview && typeof data.resume_preview === "string") {
    return (
      <p className="mt-2 line-clamp-3 text-xs text-white/45">
        Resume preview: {data.resume_preview as string}
      </p>
    );
  }
  return null;
}

function AutoScrollPre({
  text,
  className,
}: {
  text: string;
  className?: string;
}) {
  const ref = useRef<HTMLPreElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [text]);

  return (
    <pre ref={ref} className={className}>
      {text}
    </pre>
  );
}

function StreamBlock({
  title,
  text,
  mono = true,
}: {
  title: string;
  text: string;
  mono?: boolean;
}) {
  if (!text) return null;
  return (
    <Collapsible
      title={title}
      subtitle={`${text.length.toLocaleString()} chars`}
      defaultOpen
      className="mt-2"
    >
      <AutoScrollPre
        text={text}
        className={`max-h-64 overflow-y-auto overflow-x-hidden whitespace-pre-wrap rounded-lg bg-black/40 p-3 text-xs leading-relaxed text-white/75 [overflow-wrap:anywhere] ${
          mono ? "font-mono" : ""
        }`}
      />
    </Collapsible>
  );
}

function ResumeSkillCards({ skills }: { skills: ResumeSkill[] }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {skills.map((s, i) => (
        <Collapsible
          key={`${s.skill_name}-${i}`}
          title={s.skill_name}
          defaultOpen={false}
        >
          {s.context_depth ? (
            <p className="text-sm leading-relaxed text-white/65">{s.context_depth}</p>
          ) : (
            <p className="text-xs text-white/40">No context captured.</p>
          )}
        </Collapsible>
      ))}
    </div>
  );
}

function CandidatesTable({
  candidates,
}: {
  candidates: Array<{
    rank?: number;
    name?: string;
    canonical_id?: string;
    score?: number;
  }>;
}) {
  if (!candidates?.length) return null;
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-white/10">
      <table className="w-full text-left text-xs">
        <thead className="bg-white/5 text-white/50">
          <tr>
            <th className="px-2 py-1.5">#</th>
            <th className="px-2 py-1.5">Name</th>
            <th className="px-2 py-1.5">ID</th>
            <th className="px-2 py-1.5">Score</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, i) => (
            <tr key={i} className="border-t border-white/5 text-white/70">
              <td className="px-2 py-1.5">{c.rank ?? i + 1}</td>
              <td className="px-2 py-1.5">{c.name}</td>
              <td className="px-2 py-1.5 font-mono text-[10px] text-white/45">
                {c.canonical_id}
              </td>
              <td className="px-2 py-1.5">{c.score?.toFixed?.(3) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function gapCategoryClass(cat: string): string {
  switch (cat) {
    case "critical":
      return "border-rose-500/30 bg-rose-500/10 text-rose-200";
    case "moderate":
      return "border-amber-500/30 bg-amber-500/10 text-amber-200";
    case "minor":
      return "border-sky-500/30 bg-sky-500/10 text-sky-200";
    case "met":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
    default:
      return "border-white/15 bg-white/5 text-white/60";
  }
}

function streamSignature(streams: Record<string, StreamBuffers>): string {
  let s = "";
  for (const k of Object.keys(streams)) {
    const v = streams[k];
    s += `${k}:${v.reasoning.length}:${v.content.length};`;
  }
  return s;
}

export function EmployeeEventTree({
  events,
  streams,
  streamKey,
  wsOpen,
  wsStatus,
  scrollParentRef,
}: {
  events: NormalizedEmployeeEvent[];
  streams: Record<string, StreamBuffers>;
  streamKey: (phase: string, step: string) => string;
  wsOpen: boolean;
  wsStatus: "idle" | "connecting" | "open" | "closed" | "error";
  scrollParentRef?: RefObject<HTMLElement | null>;
}) {
  const byPhase = useMemo(() => {
    const m: Record<string, NormalizedEmployeeEvent[]> = {};
    for (const p of EMPLOYEE_PHASE_ORDER) m[p] = [];
    for (const e of events) {
      if (!m[e.phase]) m[e.phase] = [];
      m[e.phase].push(e);
    }
    return m;
  }, [events]);

  const livePhase = useMemo((): EmployeePhase | null => {
    const skRes = streamKey("resume_extraction", "llm_extraction_streaming");
    const skMas = streamKey("mastery", "mastery_scoring_streaming");

    const resumeEnded = events.some(
      (e) =>
        e.phase === "resume_extraction" &&
        e.type === "stream_end" &&
        e.step === "llm_extraction_streaming"
    );
    const masteryEnded = events.some(
      (e) =>
        e.phase === "mastery" &&
        e.type === "stream_end" &&
        e.step === "mastery_scoring_streaming"
    );

    const resBuf = streams[skRes];
    const masBuf = streams[skMas];
    const resumeStreaming =
      !resumeEnded &&
      Boolean(
        (resBuf?.reasoning && resBuf.reasoning.length > 0) ||
          (resBuf?.content && resBuf.content.length > 0)
      );
    const masteryStreaming =
      !masteryEnded &&
      Boolean(
        (masBuf?.reasoning && masBuf.reasoning.length > 0) ||
          (masBuf?.content && masBuf.content.length > 0)
      );

    if ((wsOpen || wsStatus === "connecting") && events.length === 0) {
      return "resume_extraction";
    }
    if (resumeStreaming) return "resume_extraction";
    if (masteryStreaming) return "mastery";

    const last = events[events.length - 1];
    if (last && isEmployeePhase(last.phase)) return last.phase;

    if (wsOpen || wsStatus === "connecting") return "resume_extraction";
    return null;
  }, [events, streams, streamKey, wsOpen, wsStatus]);

  const streamSig = useMemo(() => streamSignature(streams), [streams]);

  const activeStepScrollTarget = useMemo((): string | null => {
    const skRes = streamKey("resume_extraction", "llm_extraction_streaming");
    const skMas = streamKey("mastery", "mastery_scoring_streaming");

    const resumeEnded = events.some(
      (e) =>
        e.phase === "resume_extraction" &&
        e.type === "stream_end" &&
        e.step === "llm_extraction_streaming"
    );
    const masteryEnded = events.some(
      (e) =>
        e.phase === "mastery" &&
        e.type === "stream_end" &&
        e.step === "mastery_scoring_streaming"
    );

    const resBuf = streams[skRes];
    const masBuf = streams[skMas];
    const resumeStreaming =
      !resumeEnded &&
      Boolean(
        (resBuf?.reasoning && resBuf.reasoning.length > 0) ||
          (resBuf?.content && resBuf.content.length > 0)
      );
    const masteryStreaming =
      !masteryEnded &&
      Boolean(
        (masBuf?.reasoning && masBuf.reasoning.length > 0) ||
          (masBuf?.content && masBuf.content.length > 0)
      );

    if (resumeStreaming) return "stream-resume";
    if (masteryStreaming) return "stream-mastery";

    const last = events[events.length - 1];
    if (!last) return null;

    if (
      last.phase === "resume_extraction" &&
      last.type === "result" &&
      last.step === "llm_extraction_done"
    ) {
      return "resume-result";
    }
    if (
      last.phase === "mastery" &&
      last.type === "result" &&
      last.step === "mastery_scoring_done"
    ) {
      return "mastery-result";
    }
    if (
      last.phase === "gap" &&
      last.type === "result" &&
      last.step === "gap_analysis_done"
    ) {
      return "gap-result";
    }

    return last.id;
  }, [events, streams, streamKey]);

  useLayoutEffect(() => {
    const root = scrollParentRef?.current;
    if (!root || !activeStepScrollTarget) return;

    requestAnimationFrame(() => {
      const safe =
        typeof CSS !== "undefined" && typeof CSS.escape === "function"
          ? CSS.escape(activeStepScrollTarget)
          : activeStepScrollTarget.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
      const el = root.querySelector(`[data-orch-step="${safe}"]`);
      el?.scrollIntoView({ block: "nearest", behavior: "auto" });
    });
  }, [activeStepScrollTarget, streamSig, scrollParentRef, livePhase]);

  const resumeResult = useMemo(() => {
    const list = byPhase.resume_extraction ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "llm_extraction_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.resume_extraction]);

  const resumeSkills: ResumeSkill[] = useMemo(() => {
    if (!resumeResult?.data?.skills || !Array.isArray(resumeResult.data.skills)) {
      return [];
    }
    return resumeResult.data.skills as ResumeSkill[];
  }, [resumeResult]);

  const masteryResult = useMemo(() => {
    const list = byPhase.mastery ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "mastery_scoring_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.mastery]);

  const gapResult = useMemo(() => {
    const list = byPhase.gap ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "gap_analysis_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.gap]);

  const showConnecting =
    wsStatus === "connecting" && events.length === 0 && !wsOpen;

  if (!events.length && !wsOpen && wsStatus !== "connecting") {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-8 text-center text-sm text-white/45">
        Upload a resume and choose{" "}
        <span className="text-white/70">Start resume analysis</span> to stream live
        orchestration here.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {showConnecting ? (
        <p className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-sky-200">
          Connecting to live stream…
        </p>
      ) : null}

      {EMPLOYEE_PHASE_ORDER.map((phase) => {
        const phaseEvents = byPhase[phase] ?? [];
        const isActive =
          livePhase === phase &&
          (wsOpen || wsStatus === "connecting" || phaseEvents.length > 0);
        const skRes = streamKey("resume_extraction", "llm_extraction_streaming");
        const skMas = streamKey("mastery", "mastery_scoring_streaming");

        return (
          <Collapsible
            key={phase}
            defaultOpen={Boolean(isActive)}
            title={EMPLOYEE_PHASE_LABEL[phase]}
            subtitle={
              phaseEvents.length
                ? `${phaseEvents.length} events`
                : "Waiting…"
            }
            badge={
              isActive ? (
                <span className="animate-pulse-slow rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                  Live
                </span>
              ) : phaseEvents.length ? (
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/50">
                  Done
                </span>
              ) : null
            }
          >
            {phase === "resume_extraction" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => {
                  if (e.type === "result" && e.step === "llm_extraction_done") {
                    return null;
                  }
                  return <LogRow key={e.id} ev={e} />;
                })}
                {(streams[skRes]?.reasoning || streams[skRes]?.content) && (
                  <div
                    data-orch-step="stream-resume"
                    className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-3"
                  >
                    <p className="text-xs font-medium text-violet-200/90">
                      Live LLM stream (resume)
                    </p>
                    <StreamBlock
                      title="Reasoning trace"
                      text={streams[skRes]?.reasoning ?? ""}
                    />
                    <StreamBlock
                      title="Model output (JSON)"
                      text={streams[skRes]?.content ?? ""}
                    />
                  </div>
                )}
                {resumeResult ? (
                  <div
                    data-orch-step="resume-result"
                    className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3"
                  >
                    <p className="text-sm font-medium text-emerald-100/90">
                      Extracted skills ({resumeSkills.length})
                    </p>
                    {(typeof resumeResult.data.reasoning_summary === "string" ||
                      typeof resumeResult.data.reasoning === "string") &&
                    (resumeResult.data.reasoning_summary || resumeResult.data.reasoning) ? (
                      <Collapsible
                        title="Phase reasoning summary"
                        defaultOpen={false}
                        className="mt-2 border-emerald-500/20"
                      >
                        <p className="text-sm leading-relaxed text-white/65">
                          {String(
                            resumeResult.data.reasoning_summary ??
                              resumeResult.data.reasoning ??
                              ""
                          )}
                        </p>
                      </Collapsible>
                    ) : null}
                    <ResumeSkillCards skills={resumeSkills} />
                  </div>
                ) : null}
              </div>
            ) : null}

            {phase === "normalization" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => (
                  <div key={e.id}>
                    <LogRow ev={e} />
                    {e.type === "log" &&
                    e.data.top_candidates &&
                    Array.isArray(e.data.top_candidates) ? (
                      <CandidatesTable
                        candidates={
                          e.data.top_candidates as Parameters<
                            typeof CandidatesTable
                          >[0]["candidates"]
                        }
                      />
                    ) : null}
                    {e.type === "decision" ? (
                      <div className="mt-2 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-white/70">
                        <p>
                          <span className="text-white/45">Raw: </span>
                          {String(e.data.raw_skill ?? "")}
                        </p>
                        {e.data.matched_name ? (
                          <p>
                            <span className="text-white/45">Matched: </span>
                            {String(e.data.matched_name)}
                          </p>
                        ) : null}
                        {e.data.coined_name ? (
                          <p>
                            <span className="text-white/45">Coined: </span>
                            {String(e.data.coined_name)}
                          </p>
                        ) : null}
                        {e.data.canonical_id ? (
                          <p className="font-mono text-[10px] text-white/45">
                            {String(e.data.canonical_id)}
                          </p>
                        ) : null}
                        {e.data.llm_raw_reply ? (
                          <Collapsible
                            title="LLM reply"
                            defaultOpen={false}
                            className="mt-2"
                          >
                            <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px] text-white/60">
                              {String(e.data.llm_raw_reply)}
                            </pre>
                          </Collapsible>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}

            {phase === "mastery" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => {
                  if (e.type === "result" && e.step === "mastery_scoring_done") {
                    return null;
                  }
                  return <LogRow key={e.id} ev={e} />;
                })}
                {(streams[skMas]?.reasoning || streams[skMas]?.content) && (
                  <div
                    data-orch-step="stream-mastery"
                    className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"
                  >
                    <p className="text-xs font-medium text-amber-200/90">
                      Live mastery scoring stream
                    </p>
                    <StreamBlock
                      title="Reasoning trace"
                      text={streams[skMas]?.reasoning ?? ""}
                    />
                    <StreamBlock
                      title="Model output (JSON)"
                      text={streams[skMas]?.content ?? ""}
                    />
                  </div>
                )}
                {masteryResult?.data?.skills &&
                Array.isArray(masteryResult.data.skills) ? (
                  <div
                    data-orch-step="mastery-result"
                    className="overflow-x-auto rounded-xl border border-white/10"
                  >
                    {typeof masteryResult.data.reasoning_summary === "string" &&
                    masteryResult.data.reasoning_summary ? (
                      <Collapsible
                        title="Reasoning summary (truncated)"
                        defaultOpen={false}
                        className="mb-3 border-white/10"
                      >
                        <p className="px-3 pb-2 text-sm leading-relaxed text-white/65">
                          {masteryResult.data.reasoning_summary as string}
                        </p>
                      </Collapsible>
                    ) : null}
                    <table className="w-full min-w-[480px] text-left text-xs">
                      <thead className="bg-white/5 text-white/50">
                        <tr>
                          <th className="px-3 py-2">Skill</th>
                          <th className="px-3 py-2">Depth</th>
                          <th className="px-3 py-2">Mastery</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(masteryResult.data.skills as Record<string, unknown>[]).map(
                          (row, i) => (
                            <tr
                              key={i}
                              className="border-t border-white/5 text-white/75"
                            >
                              <td className="px-3 py-2 font-medium">
                                {String(row.skill_name ?? "")}
                              </td>
                              <td className="px-3 py-2">
                                {String(row.depth_level ?? "")}
                              </td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.current_mastery === "number"
                                  ? row.current_mastery.toFixed(2)
                                  : String(row.current_mastery ?? "")}
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            ) : null}

            {phase === "gap" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => {
                  if (e.type === "result" && e.step === "gap_analysis_done") {
                    return null;
                  }
                  return <LogRow key={e.id} ev={e} />;
                })}
                {gapResult?.data?.ranked_gaps &&
                Array.isArray(gapResult.data.ranked_gaps) ? (
                  <div
                    data-orch-step="gap-result"
                    className="overflow-x-auto rounded-xl border border-white/10"
                  >
                    <table className="w-full min-w-[640px] text-left text-xs">
                      <thead className="bg-white/5 text-white/50">
                        <tr>
                          <th className="px-3 py-2">Skill</th>
                          <th className="px-3 py-2">Tier</th>
                          <th className="px-3 py-2">Target</th>
                          <th className="px-3 py-2">Current</th>
                          <th className="px-3 py-2">Gap</th>
                          <th className="px-3 py-2">Category</th>
                          <th className="px-3 py-2">Priority</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(gapResult.data.ranked_gaps as Record<string, unknown>[]).map(
                          (row, i) => (
                            <tr
                              key={i}
                              className="border-t border-white/5 text-white/75"
                            >
                              <td className="px-3 py-2 font-medium">
                                {String(row.skill_name ?? "")}
                              </td>
                              <td className="px-3 py-2">{String(row.tier ?? "")}</td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.target_mastery === "number"
                                  ? row.target_mastery.toFixed(2)
                                  : String(row.target_mastery ?? "")}
                              </td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.current_mastery === "number"
                                  ? row.current_mastery.toFixed(2)
                                  : String(row.current_mastery ?? "")}
                              </td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.gap === "number"
                                  ? row.gap.toFixed(3)
                                  : String(row.gap ?? "")}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  className={`inline-block rounded-full border px-2 py-0.5 text-[10px] uppercase ${gapCategoryClass(
                                    String(row.gap_category ?? "")
                                  )}`}
                                >
                                  {String(row.gap_category ?? "")}
                                </span>
                              </td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.priority_score === "number"
                                  ? row.priority_score.toFixed(3)
                                  : String(row.priority_score ?? "")}
                              </td>
                            </tr>
                          )
                        )}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            ) : null}

            {phase === "db" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => (
                  <LogRow key={e.id} ev={e} />
                ))}
              </div>
            ) : null}

            {phase === "path" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => (
                  <LogRow key={e.id} ev={e} />
                ))}
              </div>
            ) : null}

            {phase === "journey" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => (
                  <LogRow key={e.id} ev={e} />
                ))}
              </div>
            ) : null}
          </Collapsible>
        );
      })}
    </div>
  );
}
