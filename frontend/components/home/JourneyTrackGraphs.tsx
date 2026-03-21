"use client";

import { useMemo, useRef, useState } from "react";

type TrackKey = "sprint" | "balanced" | "quality";

type CourseInfo = {
  title: string;
  duration: string;
  institution: string;
  rating: number | null;
};

type TwigNode = {
  id: string;
  label: string;
};

type BranchNode = {
  id: string;
  label: string;
  stage: number;
  gap: number;
  severity: string;
  borderColor: string;
  twigs: TwigNode[];
  courseOptions: Record<TrackKey, CourseInfo | null>;
};

function asObj(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function asNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function parseCourse(v: unknown): CourseInfo | null {
  const o = asObj(v);
  if (!o) return null;
  return {
    title: String(o.title ?? "").trim(),
    duration: String(o.duration ?? "").trim(),
    institution: String(o.institution ?? "").trim(),
    rating: typeof o.rating === "number" ? o.rating : null,
  };
}

function parseJourney(data: Record<string, unknown>) {
  const narratives = asObj(data.narratives) ?? {};
  const pathSummaries = asObj(data.path_summaries) ?? {};
  const validation = asObj(data.validation) ?? {};
  const tree = asObj(data.tree) ?? {};
  const root = asObj(tree.root) ?? {};
  const roleLabel = String(root.label ?? "Role");
  const rawChildren = Array.isArray(root.children) ? root.children : [];

  const nodes: BranchNode[] = [];
  for (const child of rawChildren) {
    const c = asObj(child);
    if (!c) continue;
    const childNodes = Array.isArray(c.children) ? c.children : [];
    const twigs = childNodes
      .map((t) => asObj(t))
      .filter(Boolean)
      .map((t) => ({
        id: String((t as Record<string, unknown>).id ?? `${String(c.id ?? "twig")}-twig`),
        label: String((t as Record<string, unknown>).label ?? "Prerequisite"),
      }));

    const options = asObj(c.course_options) ?? {};
    nodes.push({
      id: String(c.id ?? `skill-${nodes.length + 1}`),
      label: String(c.label ?? "Skill"),
      stage: Number(c.stage ?? 1),
      gap: typeof c.gap === "number" ? c.gap : 0,
      severity: String(c.severity ?? "moderate"),
      borderColor: String(c.border_color ?? "#F59E0B"),
      twigs,
      courseOptions: {
        sprint: parseCourse(options.sprint),
        balanced: parseCourse(options.balanced),
        quality: parseCourse(options.quality),
      },
    });
  }

  const tracks: Array<{
    key: TrackKey;
    level: string;
    title: string;
    weeks: number | null;
    coverage: number | null;
    narrative: string;
    accent: string;
  }> = [
    {
      key: "sprint",
      level: "Beginner",
      title: "Sprint track",
      weeks: asNumber(asObj(pathSummaries.sprint)?.total_weeks),
      coverage: (() => {
        const score = asNumber(asObj(pathSummaries.sprint)?.coverage_score);
        if (score === null) return null;
        return Math.round((score <= 1 ? score * 100 : score) * 10) / 10;
      })(),
      narrative: String(narratives.sprint ?? ""),
      accent: "border-emerald-500/30 bg-emerald-500/10",
    },
    {
      key: "balanced",
      level: "Intermediate",
      title: "Balanced track",
      weeks: asNumber(asObj(pathSummaries.balanced)?.total_weeks),
      coverage: (() => {
        const score = asNumber(asObj(pathSummaries.balanced)?.coverage_score);
        if (score === null) return null;
        return Math.round((score <= 1 ? score * 100 : score) * 10) / 10;
      })(),
      narrative: String(narratives.balanced ?? ""),
      accent: "border-amber-500/30 bg-amber-500/10",
    },
    {
      key: "quality",
      level: "Advanced",
      title: "Quality track",
      weeks: asNumber(asObj(pathSummaries.quality)?.total_weeks),
      coverage: (() => {
        const score = asNumber(asObj(pathSummaries.quality)?.coverage_score);
        if (score === null) return null;
        return Math.round((score <= 1 ? score * 100 : score) * 10) / 10;
      })(),
      narrative: String(narratives.quality ?? ""),
      accent: "border-violet-500/30 bg-violet-500/10",
    },
  ];

  return {
    roleLabel,
    nodes,
    tracks,
    validationNotes: String(validation.notes ?? ""),
  };
}

function JourneyGraph({ nodes }: { nodes: BranchNode[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState<{
    x: number;
    y: number;
    node: BranchNode;
  } | null>(null);

  const rows = useMemo(() => {
    const sorted = [...nodes].sort((a, b) =>
      a.stage === b.stage ? a.label.localeCompare(b.label) : a.stage - b.stage
    );

    const labelToStage = new Map<string, number>();
    for (const n of sorted) {
      labelToStage.set(n.label.trim().toLowerCase(), n.stage);
    }

    return sorted.map((n) => {
      const depStages = Array.from(
        new Set(
          n.twigs
            .map((t) => labelToStage.get(t.label.trim().toLowerCase()))
            .filter((v): v is number => typeof v === "number")
        )
      ).sort((a, b) => a - b);
      const stageChain = [n.stage, ...depStages.filter((s) => s !== n.stage)];
      return {
        node: n,
        stageChain: stageChain.length ? stageChain : [n.stage],
      };
    });
  }, [nodes]);

  return (
    <div ref={containerRef} className="relative mt-3 rounded-xl border border-white/10 bg-black/25 p-4">
      <div className="relative pl-6">
        <div className="absolute bottom-3 left-2 top-3 w-px bg-white/20" />

        {rows.map((row, idx) => {
          const n = row.node;
          const fill = n.severity === "critical" ? "bg-rose-900/75" : "bg-amber-900/70";
          return (
            <div
              key={n.id}
              className={`relative mb-5 rounded-xl border border-white/10 bg-white/[0.02] p-3 ${
                idx === rows.length - 1 ? "mb-0" : ""
              }`}
            >
              <div className="absolute -left-[18px] top-7 h-3 w-3 rounded-full border border-white/40 bg-slate-950" />

              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:gap-5">
                <button
                  type="button"
                  className={`w-full max-w-xl rounded-xl border border-white/20 px-4 py-3 text-left shadow-sm ${fill}`}
                  onMouseLeave={() => setHovered(null)}
                  onMouseMove={(e) => {
                    const host = containerRef.current;
                    if (!host) return;
                    const r = host.getBoundingClientRect();
                    setHovered({
                      x: e.clientX - r.left + 14,
                      y: e.clientY - r.top + 14,
                      node: n,
                    });
                  }}
                >
                  <p className="text-sm font-semibold text-white">{n.label}</p>
                  <p className="mt-1 text-xs text-white/80">Main type</p>
                </button>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {row.stageChain.map((s, i) => (
                      <div key={`${n.id}-stage-${s}-${i}`} className="flex items-center gap-2">
                        <span className="rounded-lg border border-slate-400/40 bg-slate-800 px-3 py-1 text-xs text-slate-100">
                          {`Stage ${s}`}
                        </span>
                        {i < row.stageChain.length - 1 ? (
                          <span className="text-white/65">→</span>
                        ) : null}
                      </div>
                    ))}
                    <span className="rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[11px] text-white/70">
                      {`Gap ${(n.gap * 100).toFixed(0)}%`}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-wrap gap-2">
                    {n.twigs.length ? (
                      n.twigs.map((t) => (
                        <span
                          key={t.id}
                          className="rounded-full border border-slate-400/30 bg-slate-900/80 px-2.5 py-1 text-[11px] text-slate-200"
                        >
                          {t.label}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-white/50">No child dependency</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {hovered ? (
        <div
          className="pointer-events-none absolute z-10 max-w-[420px] rounded-lg border border-white/20 bg-slate-900/95 p-3 text-xs text-white shadow-xl"
          style={{ left: hovered.x, top: hovered.y }}
        >
          <p className="text-sm font-semibold">{hovered.node.label}</p>
          <p className="mt-0.5 text-white/70">
            {`Stage ${hovered.node.stage} · ${hovered.node.severity} · Gap ${(hovered.node.gap * 100).toFixed(0)}%`}
          </p>
          <div className="mt-2 space-y-2">
            {(["sprint", "balanced", "quality"] as const).map((k) => {
              const c = hovered.node.courseOptions[k];
              return (
                <div key={k} className="rounded border border-white/10 bg-white/5 p-2">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-white/60">
                    {k}
                  </p>
                  {c ? (
                    <>
                      <p className="text-white/90">{c.title || "Untitled course"}</p>
                      <p className="text-white/70">
                        {c.duration || "duration n/a"} · {c.institution || "institution n/a"}
                      </p>
                      <p className="text-white/70">
                        Rating: {c.rating !== null ? c.rating : "n/a"}
                      </p>
                    </>
                  ) : (
                    <p className="text-white/60">No course data</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function JourneyTrackGraphs({
  journeyData,
}: {
  journeyData: Record<string, unknown>;
}) {
  const parsed = useMemo(() => parseJourney(journeyData), [journeyData]);

  if (!parsed.nodes.length) return null;

  return (
    <section className="mt-6 rounded-2xl border border-fuchsia-500/20 bg-fuchsia-500/[0.03] p-4 sm:p-5">
      <h3 className="text-lg font-semibold text-white/95">
        {`Phase 11 journey roadmap — ${parsed.roleLabel}`}
      </h3>
      {parsed.validationNotes ? (
        <p className="mt-1 text-xs text-white/60">Validation: {parsed.validationNotes}</p>
      ) : null}

      <div className="mt-4 space-y-3">
        {parsed.tracks.map((track) => (
          <article key={track.key} className={`rounded-xl border p-3 ${track.accent}`}>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-white/75">
              {track.level}
            </p>
            <p className="text-lg font-semibold text-white/95">{track.title}</p>
            {track.narrative ? (
              <p className="mt-2 text-sm leading-relaxed text-white/90">{track.narrative}</p>
            ) : null}
          </article>
        ))}
      </div>

      <JourneyGraph nodes={parsed.nodes} />
    </section>
  );
}

