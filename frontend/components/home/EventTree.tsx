"use client";

import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  PHASE_LABEL,
  PHASE_ORDER,
  type NormalizedEmployerEvent,
  type Phase,
  isPhase,
} from "@/lib/employerTypes";
import { Collapsible } from "@/components/Collapsible";
import type { StreamBuffers } from "@/hooks/useEmployerPipeline";

interface JdSkill {
  skill_name: string;
  jd_level?: string;
  category?: string;
  reasoning?: string;
}

function LogRow({ ev }: { ev: NormalizedEmployerEvent }) {
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
  if (data.jd_preview && typeof data.jd_preview === "string") {
    return (
      <p className="mt-2 line-clamp-3 text-xs text-white/45">
        JD preview: {data.jd_preview as string}
      </p>
    );
  }
  if (data.team_preview && typeof data.team_preview === "string") {
    return (
      <p className="mt-2 line-clamp-2 text-xs text-white/45">
        Team preview: {data.team_preview as string}
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

function SkillCards({ skills }: { skills: JdSkill[] }) {
  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {skills.map((s, i) => (
        <Collapsible
          key={`${s.skill_name}-${i}`}
          title={s.skill_name}
          subtitle={
            <span className="text-white/45">
              {[s.jd_level, s.category].filter(Boolean).join(" · ")}
            </span>
          }
          defaultOpen={false}
          badge={
            s.category ? (
              <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] uppercase text-white/50">
                {s.category}
              </span>
            ) : null
          }
        >
          {s.reasoning ? (
            <p className="text-sm leading-relaxed text-white/65">{s.reasoning}</p>
          ) : (
            <p className="text-xs text-white/40">No per-skill reasoning.</p>
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

function streamSignature(streams: Record<string, StreamBuffers>): string {
  let s = "";
  for (const k of Object.keys(streams)) {
    const v = streams[k];
    s += `${k}:${v.reasoning.length}:${v.content.length};`;
  }
  return s;
}

export function EventTree({
  events,
  streams,
  streamKey,
  wsOpen,
  scrollParentRef,
}: {
  events: NormalizedEmployerEvent[];
  streams: Record<string, StreamBuffers>;
  streamKey: (phase: string, step: string) => string;
  wsOpen: boolean;
  scrollParentRef?: RefObject<HTMLElement | null>;
}) {
  const byPhase = useMemo(() => {
    const m: Record<string, NormalizedEmployerEvent[]> = {};
    for (const p of PHASE_ORDER) m[p] = [];
    for (const e of events) {
      if (!m[e.phase]) m[e.phase] = [];
      m[e.phase].push(e);
    }
    return m;
  }, [events]);

  const livePhase = useMemo((): Phase | null => {
    if (!wsOpen && events.length === 0) return null;

    const skJd = streamKey("jd_extraction", "llm_extraction_streaming");
    const skTeam = streamKey("team_context", "team_analysis_streaming");

    const jdEnded = events.some(
      (e) =>
        e.phase === "jd_extraction" &&
        e.type === "stream_end" &&
        e.step === "llm_extraction_streaming"
    );
    const teamEnded = events.some(
      (e) =>
        e.phase === "team_context" &&
        e.type === "stream_end" &&
        e.step === "team_analysis_streaming"
    );

    const jdBuf = streams[skJd];
    const teamBuf = streams[skTeam];
    const jdStreaming =
      !jdEnded &&
      Boolean(
        (jdBuf?.reasoning && jdBuf.reasoning.length > 0) ||
          (jdBuf?.content && jdBuf.content.length > 0)
      );
    const teamStreaming =
      !teamEnded &&
      Boolean(
        (teamBuf?.reasoning && teamBuf.reasoning.length > 0) ||
          (teamBuf?.content && teamBuf.content.length > 0)
      );

    if (wsOpen && events.length === 0) return "jd_extraction";
    if (jdStreaming) return "jd_extraction";
    if (teamStreaming) return "team_context";

    const last = events[events.length - 1];
    if (last && isPhase(last.phase)) return last.phase;

    if (wsOpen) return "jd_extraction";
    return null;
  }, [events, streams, streamKey, wsOpen]);

  const [phaseOpen, setPhaseOpen] = useState<Partial<Record<Phase, boolean>>>(
    {}
  );

  useLayoutEffect(() => {
    if (!livePhase) return;
    setPhaseOpen((prev) => {
      const next = { ...prev };
      const idx = PHASE_ORDER.indexOf(livePhase);
      for (let i = 0; i < idx; i++) {
        next[PHASE_ORDER[i]] = false;
      }
      next[livePhase] = true;
      return next;
    });
  }, [livePhase]);

  const streamSig = useMemo(() => streamSignature(streams), [streams]);

  const activeStepScrollTarget = useMemo((): string | null => {
    const skJd = streamKey("jd_extraction", "llm_extraction_streaming");
    const skTeam = streamKey("team_context", "team_analysis_streaming");

    const jdEnded = events.some(
      (e) =>
        e.phase === "jd_extraction" &&
        e.type === "stream_end" &&
        e.step === "llm_extraction_streaming"
    );
    const teamEnded = events.some(
      (e) =>
        e.phase === "team_context" &&
        e.type === "stream_end" &&
        e.step === "team_analysis_streaming"
    );

    const jdBuf = streams[skJd];
    const teamBuf = streams[skTeam];
    const jdStreaming =
      !jdEnded &&
      Boolean(
        (jdBuf?.reasoning && jdBuf.reasoning.length > 0) ||
          (jdBuf?.content && jdBuf.content.length > 0)
      );
    const teamStreaming =
      !teamEnded &&
      Boolean(
        (teamBuf?.reasoning && teamBuf.reasoning.length > 0) ||
          (teamBuf?.content && teamBuf.content.length > 0)
      );

    if (jdStreaming) return "stream-jd";
    if (teamStreaming) return "stream-team";

    const last = events[events.length - 1];
    if (!last) return null;

    if (
      last.phase === "jd_extraction" &&
      last.type === "result" &&
      last.step === "llm_extraction_done"
    ) {
      return "jd-result";
    }
    if (
      last.phase === "team_context" &&
      last.type === "result" &&
      last.step === "team_analysis_done"
    ) {
      return "team-result";
    }
    if (
      last.phase === "mastery" &&
      last.type === "result" &&
      last.step === "mastery_matrix_done"
    ) {
      return "mastery-result";
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

  const jdResult = useMemo(() => {
    const list = byPhase.jd_extraction ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "llm_extraction_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.jd_extraction]);

  const jdSkills: JdSkill[] = useMemo(() => {
    if (!jdResult?.data?.skills || !Array.isArray(jdResult.data.skills)) return [];
    return jdResult.data.skills as JdSkill[];
  }, [jdResult]);

  const teamResult = useMemo(() => {
    const list = byPhase.team_context ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "team_analysis_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.team_context]);

  const masteryResult = useMemo(() => {
    const list = byPhase.mastery ?? [];
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].type === "result" && list[i].step === "mastery_matrix_done") {
        return list[i];
      }
    }
    return null;
  }, [byPhase.mastery]);

  if (!events.length && !wsOpen) {
    return (
      <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-8 text-center text-sm text-white/45">
        Run <span className="text-white/70">Start analysis</span> to stream live
        orchestration events here.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {PHASE_ORDER.map((phase) => {
        const phaseEvents = byPhase[phase] ?? [];
        const isActive = livePhase === phase && (wsOpen || phaseEvents.length > 0);
        const skJd = streamKey("jd_extraction", "llm_extraction_streaming");
        const skTeam = streamKey("team_context", "team_analysis_streaming");

        return (
          <Collapsible
            key={phase}
            open={phaseOpen[phase] ?? false}
            onOpenChange={(o) =>
              setPhaseOpen((p) => ({ ...p, [phase]: o }))
            }
            defaultOpen={false}
            title={PHASE_LABEL[phase]}
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
            {phase === "jd_extraction" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => {
                  if (e.type === "result" && e.step === "llm_extraction_done") {
                    return null;
                  }
                  return <LogRow key={e.id} ev={e} />;
                })}
                {(streams[skJd]?.reasoning || streams[skJd]?.content) && (
                  <div
                    data-orch-step="stream-jd"
                    className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-3"
                  >
                    <p className="text-xs font-medium text-violet-200/90">
                      Live LLM stream
                    </p>
                    <StreamBlock
                      title="Reasoning trace"
                      text={streams[skJd]?.reasoning ?? ""}
                    />
                    <StreamBlock
                      title="Model output (JSON)"
                      text={streams[skJd]?.content ?? ""}
                    />
                  </div>
                )}
                {jdResult ? (
                  <div
                    data-orch-step="jd-result"
                    className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-3"
                  >
                    <p className="text-sm font-medium text-emerald-100/90">
                      Extracted skills ({jdSkills.length})
                    </p>
                    {typeof jdResult.data.reasoning === "string" &&
                    jdResult.data.reasoning ? (
                      <Collapsible
                        title="Phase reasoning summary"
                        defaultOpen={false}
                        className="mt-2 border-emerald-500/20"
                      >
                        <p className="text-sm leading-relaxed text-white/65">
                          {jdResult.data.reasoning as string}
                        </p>
                      </Collapsible>
                    ) : null}
                    <SkillCards skills={jdSkills} />
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

            {phase === "team_context" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => {
                  if (e.type === "result" && e.step === "team_analysis_done") {
                    return null;
                  }
                  return <LogRow key={e.id} ev={e} />;
                })}
                {(streams[skTeam]?.reasoning || streams[skTeam]?.content) && (
                  <div
                    data-orch-step="stream-team"
                    className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-3"
                  >
                    <p className="text-xs font-medium text-sky-200/90">
                      Live team analysis stream
                    </p>
                    <StreamBlock
                      title="Reasoning trace"
                      text={streams[skTeam]?.reasoning ?? ""}
                    />
                    <StreamBlock
                      title="Model output"
                      text={streams[skTeam]?.content ?? ""}
                    />
                  </div>
                )}
                {teamResult ? (
                  <div
                    data-orch-step="team-result"
                    className="rounded-xl border border-sky-500/25 bg-sky-500/5 p-3"
                  >
                    {typeof teamResult.data.reasoning === "string" &&
                    teamResult.data.reasoning ? (
                      <Collapsible
                        title="Team analysis reasoning"
                        defaultOpen={false}
                        className="mb-3"
                      >
                        <p className="text-sm leading-relaxed text-white/65">
                          {teamResult.data.reasoning as string}
                        </p>
                      </Collapsible>
                    ) : null}
                    <p className="text-sm font-medium text-sky-100/90">Signals</p>
                    <ul className="mt-2 space-y-2">
                      {Array.isArray(teamResult.data.signals)
                        ? (teamResult.data.signals as Record<string, string>[]).map(
                            (sig, i) => (
                              <li
                                key={i}
                                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm"
                              >
                                <span className="font-medium text-white/85">
                                  {sig.skill_name}
                                </span>
                                <span className="text-xs text-white/50">
                                  {sig.recency_category}
                                </span>
                              </li>
                            )
                          )
                        : null}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {phase === "mastery" ? (
              <div className="space-y-2">
                {phaseEvents.map((e) => (
                  <LogRow key={e.id} ev={e} />
                ))}
                {masteryResult?.data?.skills &&
                Array.isArray(masteryResult.data.skills) ? (
                  <div
                    data-orch-step="mastery-result"
                    className="overflow-x-auto rounded-xl border border-white/10"
                  >
                    <table className="w-full min-w-[520px] text-left text-xs">
                      <thead className="bg-white/5 text-white/50">
                        <tr>
                          <th className="px-3 py-2">Skill</th>
                          <th className="px-3 py-2">Tier</th>
                          <th className="px-3 py-2">Recency</th>
                          <th className="px-3 py-2">Target</th>
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
                              <td className="px-3 py-2">{String(row.tier ?? "")}</td>
                              <td className="px-3 py-2">
                                {String(row.team_recency ?? "")}
                              </td>
                              <td className="px-3 py-2 font-mono">
                                {typeof row.target_mastery === "number"
                                  ? row.target_mastery.toFixed(2)
                                  : String(row.target_mastery ?? "")}
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
          </Collapsible>
        );
      })}
    </div>
  );
}
