"use client";

import { useMemo, useState } from "react";

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

function splitLabel(text: string, maxLen = 24): string[] {
  const words = text.trim().split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w;
    if (next.length <= maxLen) {
      cur = next;
      continue;
    }
    if (cur) lines.push(cur);
    cur = w;
  }
  if (cur) lines.push(cur);
  if (lines.length <= 2) return lines;
  return [lines[0], `${lines[1].slice(0, Math.max(6, maxLen - 1))}…`];
}

function JourneyGraph({ roleLabel, nodes }: { roleLabel: string; nodes: BranchNode[] }) {
  const [hovered, setHovered] = useState<{
    x: number;
    y: number;
    node: BranchNode;
  } | null>(null);

  const geometry = useMemo(() => {
    const maxStage = Math.max(1, ...nodes.map((n) => n.stage));
    const stageGroups: Record<number, BranchNode[]> = {};
    for (let s = 1; s <= maxStage; s++) stageGroups[s] = [];
    for (const n of nodes) {
      if (!stageGroups[n.stage]) stageGroups[n.stage] = [];
      stageGroups[n.stage].push(n);
    }
    for (let s = 1; s <= maxStage; s++) {
      stageGroups[s].sort((a, b) => a.label.localeCompare(b.label));
    }

    const maxNodesInStage = Math.max(1, ...Object.values(stageGroups).map((arr) => arr.length));
    const width = Math.max(1280, 400 + maxStage * 300 + 260);
    const height = Math.max(560, 180 + maxNodesInStage * 120);
    const root = { x: 120, y: Math.round(height / 2) };

    const pos: Record<string, { x: number; y: number; node: BranchNode }> = {};
    for (let s = 1; s <= maxStage; s++) {
      const arr = stageGroups[s];
      const x = 360 + (s - 1) * 280;
      const step = height / (arr.length + 1);
      arr.forEach((n, i) => {
        pos[n.id] = { x, y: Math.round((i + 1) * step), node: n };
      });
    }

    return { maxStage, width, height, root, pos, stageGroups };
  }, [nodes]);

  return (
    <div className="relative mt-3 overflow-x-auto rounded-xl border border-white/10 bg-black/25 p-3">
      <svg
        viewBox={`0 0 ${geometry.width} ${geometry.height}`}
        className="block h-auto min-w-[1024px] w-full"
      >
        {Array.from({ length: geometry.maxStage }, (_, i) => i + 1).map((stage) => {
          const x = 360 + (stage - 1) * 280;
          return (
            <text
              key={`stage-${stage}`}
              x={x}
              y={36}
              fill="#CBD5E1"
              fontSize="14"
              textAnchor="middle"
              fontWeight="600"
            >
              {`Stage ${stage}`}
            </text>
          );
        })}

        {nodes.map((n) => {
          const p = geometry.pos[n.id];
          return (
            <line
              key={`edge-root-${n.id}`}
              x1={geometry.root.x}
              y1={geometry.root.y}
              x2={p.x}
              y2={p.y}
              stroke={n.borderColor}
              strokeOpacity={0.65}
              strokeWidth={Math.max(1.8, 2.2 + n.gap * 3)}
            />
          );
        })}
        {nodes.flatMap((n) => {
          const p = geometry.pos[n.id];
          const total = n.twigs.length;
          return n.twigs.map((twig, i) => {
            const tx = p.x + 190;
            const ty = p.y + (i - (total - 1) / 2) * 42;
            return (
              <g key={`twig-${twig.id}`}>
                <line
                  x1={p.x + 96}
                  y1={p.y}
                  x2={tx - 14}
                  y2={ty}
                  stroke="#9CA3AF"
                  strokeDasharray="5 4"
                  strokeOpacity={0.8}
                  strokeWidth={1.5}
                />
                <circle cx={tx} cy={ty} r={11} fill="#0F172A" stroke="#94A3B8" />
                <text x={tx + 15} y={ty + 4} fill="#CBD5E1" fontSize="11">
                  {twig.label}
                </text>
              </g>
            );
          });
        })}

        <g>
          <circle cx={geometry.root.x} cy={geometry.root.y} r={44} fill="#1E3A8A" />
          <text x={geometry.root.x} y={geometry.root.y - 5} fill="#fff" fontSize="13" textAnchor="middle">
            Goal
          </text>
          <text x={geometry.root.x} y={geometry.root.y + 13} fill="#DBEAFE" fontSize="12" textAnchor="middle">
            {roleLabel}
          </text>
        </g>

        {nodes.map((n) => {
          const p = geometry.pos[n.id];
          const fill = n.severity === "critical" ? "#7F1D1D" : "#713F12";
          const lines = splitLabel(n.label);
          return (
            <g key={`node-${n.id}`}>
              <rect
                x={p.x - 96}
                y={p.y - 30}
                width={192}
                height={60}
                rx={14}
                fill={fill}
                stroke={n.borderColor}
                strokeWidth={2}
                onMouseLeave={() => setHovered(null)}
                onMouseMove={(e) => {
                  const box = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect();
                  setHovered({
                    x: e.clientX - box.left + 12,
                    y: e.clientY - box.top + 12,
                    node: n,
                  });
                }}
              />
              <text x={p.x} y={p.y - 7} fill="#fff" fontSize="11" textAnchor="middle">
                {lines[0]}
              </text>
              <text x={p.x} y={p.y + 7} fill="#fff" fontSize="11" textAnchor="middle">
                {lines[1] ?? ""}
              </text>
              <text x={p.x} y={p.y + 20} fill="#E5E7EB" fontSize="10" textAnchor="middle">
                {`Stage ${n.stage} · Gap ${(n.gap * 100).toFixed(0)}%`}
              </text>
            </g>
          );
        })}
      </svg>

      {hovered ? (
        <div
          className="pointer-events-none absolute z-10 max-w-[380px] rounded-lg border border-white/20 bg-slate-900/95 p-3 text-xs text-white shadow-xl"
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
      <h3 className="text-lg font-semibold text-white/95">Phase 11 journey roadmap</h3>
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
            <p className="mt-1 text-sm text-white/85">
              {track.weeks !== null ? `${track.weeks} weeks` : "Weeks n/a"} ·{" "}
              {track.coverage !== null ? `${track.coverage}% coverage` : "Coverage n/a"}
            </p>
            {track.narrative ? (
              <p className="mt-2 text-sm leading-relaxed text-white/90">{track.narrative}</p>
            ) : null}
          </article>
        ))}
      </div>

      <JourneyGraph roleLabel={parsed.roleLabel} nodes={parsed.nodes} />
    </section>
  );
}

