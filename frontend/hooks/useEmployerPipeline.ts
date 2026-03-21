"use client";

import { useCallback, useRef, useState } from "react";
import type { NormalizedEmployerEvent } from "@/lib/employerTypes";
import { API_BASE, employerSetupUrl as setupUrl, employerWsUrl as wsUrl } from "@/lib/config";

export type LayoutFocus = "balanced" | "employer" | "resume";

export interface StreamBuffers {
  reasoning: string;
  content: string;
}

interface HistoricalRoleData {
  id: string;
  title: string;
  seniority: string;
  jd_text?: string;
  team_context_text?: string;
  status?: string;
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useEmployerPipeline() {
  const [events, setEvents] = useState<NormalizedEmployerEvent[]>([]);
  const [streams, setStreams] = useState<Record<string, StreamBuffers>>({});
  const [roleId, setRoleId] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<
    "idle" | "connecting" | "open" | "closed" | "error"
  >("idle");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitState, setSubmitState] = useState<
    "idle" | "submitting" | "streaming" | "done" | "error"
  >("idle");
  const [pipelineDone, setPipelineDone] = useState(false);
  const [historicalData, setHistoricalData] = useState<HistoricalRoleData | null>(null);
  const [historicalLoading, setHistoricalLoading] = useState(false);
  const [historicalMode, setHistoricalMode] = useState(false);
  const [resetVersion, setResetVersion] = useState(0);
  const [layoutFocus, setLayoutFocus] = useState<LayoutFocus>("balanced");
  const wsRef = useRef<WebSocket | null>(null);

  const streamKey = (phase: string, step: string) => `${phase}::${step}`;

  const appendStream = useCallback(
    (phase: string, step: string, chunkType: string, text: string) => {
      const k = streamKey(phase, step);
      setStreams((prev) => {
        const cur = prev[k] ?? { reasoning: "", content: "" };
        if (chunkType === "reasoning") {
          return { ...prev, [k]: { ...cur, reasoning: cur.reasoning + text } };
        }
        if (chunkType === "content") {
          return { ...prev, [k]: { ...cur, content: cur.content + text } };
        }
        return { ...prev, [k]: cur };
      });
    },
    []
  );

  const connectWs = useCallback(
    (rid: string) => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setHistoricalMode(false);
      setWsStatus("connecting");
      setPipelineDone(false);
      setLayoutFocus("employer");
      setSubmitState("streaming");
      const socket = new WebSocket(wsUrl(rid));
      wsRef.current = socket;

      socket.onopen = () => {
        setWsStatus("open");
        setLayoutFocus("employer");
      };

      socket.onmessage = (ev) => {
        try {
          const raw = JSON.parse(ev.data as string) as Record<string, unknown>;
          const phase = String(raw.phase ?? "");
          const type = String(raw.type ?? "");
          const step = String(raw.step ?? "");
          const message = String(raw.message ?? "");
          const model = raw.model as string | null | undefined;
          const data =
            raw.data && typeof raw.data === "object"
              ? (raw.data as Record<string, unknown>)
              : {};

          if (type === "stream_chunk") {
            const chunkType = String(data.chunk_type ?? "");
            const text = String(data.text ?? "");
            appendStream(phase, step, chunkType, text);
            return;
          }

          const normalized: NormalizedEmployerEvent = {
            id: uid(),
            receivedAt: Date.now(),
            role_id: raw.role_id as string | undefined,
            phase,
            type,
            step,
            message,
            model: model ?? null,
            data,
          };

          setEvents((prev) => [...prev, normalized]);

          // Auto-focus the active work pane during employer orchestration.
          if (
            phase === "jd_extraction" ||
            phase === "normalization" ||
            phase === "team_context" ||
            phase === "mastery"
          ) {
            setLayoutFocus("employer");
          }
          if (phase === "db" && type === "complete") {
            setPipelineDone(true);
            setLayoutFocus("resume");
            setSubmitState("done");
          }
        } catch {
          /* ignore malformed */
        }
      };

      socket.onerror = () => {
        setWsStatus("error");
        setSubmitState("error");
      };

      socket.onclose = () => {
        setWsStatus((s) => (s === "connecting" ? "error" : "closed"));
        wsRef.current = null;
      };
    },
    [appendStream]
  );

  const startAnalysis = useCallback(
    async (form: FormData) => {
      setSubmitError(null);
      setSubmitState("submitting");
      setEvents([]);
      setStreams({});
      setRoleId(null);
      setPipelineDone(false);
      setHistoricalData(null);
      setHistoricalMode(false);

      const title = (form.get("title") as string)?.trim();
      const seniority = (form.get("seniority") as string)?.trim();
      if (!title || !seniority) {
        setSubmitError("Title and seniority are required.");
        return;
      }

      const hasJdFile = form.get("jd_file") instanceof File && (form.get("jd_file") as File).size > 0;
      const jdText = (form.get("jd_text") as string)?.trim() ?? "";
      if (!hasJdFile && !jdText) {
        setSubmitError("Provide a JD file or paste JD text.");
        setSubmitState("error");
        return;
      }

      const hasTeamFile =
        form.get("team_context_file") instanceof File &&
        (form.get("team_context_file") as File).size > 0;
      const teamText = (form.get("team_context_text") as string)?.trim() ?? "";
      if (!hasTeamFile && !teamText) {
        setSubmitError("Provide a Team Context file or paste Team Context text.");
        setSubmitState("error");
        return;
      }

      try {
        const res = await fetch(setupUrl(), {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || res.statusText);
        }
        const body = (await res.json()) as { id: string };
        if (!body.id) throw new Error("No role id returned");
        setRoleId(body.id);
        setLayoutFocus("employer");
        connectWs(body.id);
      } catch (e) {
        setSubmitError(e instanceof Error ? e.message : "Setup failed");
        setSubmitState("error");
      }
    },
    [connectWs]
  );

  const loadRoleById = useCallback(async (id: string) => {
    if (!id) return;
    wsRef.current?.close();
    wsRef.current = null;
    setHistoricalLoading(true);
    setSubmitError(null);
    setSubmitState("idle");
    setWsStatus("closed");
    setLayoutFocus("employer");
    setRoleId(id);
    setPipelineDone(false);

    try {
      const roleRes = await fetch(`${API_BASE}/api/v1/employer/roles/${encodeURIComponent(id)}`);
      if (!roleRes.ok) {
        const errText = await roleRes.text();
        throw new Error(errText || roleRes.statusText);
      }
      const role = (await roleRes.json()) as Record<string, unknown>;
      setHistoricalData({
        id: String(role.id ?? id),
        title: String(role.title ?? ""),
        seniority: String(role.seniority ?? ""),
        jd_text: typeof role.jd_text === "string" ? role.jd_text : "",
        team_context_text:
          typeof role.team_context_text === "string" ? role.team_context_text : "",
        status: typeof role.status === "string" ? role.status : undefined,
      });

      let rawEvents: unknown[] = [];
      try {
        const eventsRes = await fetch(
          `${API_BASE}/api/v1/employer/roles/${encodeURIComponent(id)}/events`
        );
        if (eventsRes.ok) {
          const payload = (await eventsRes.json()) as unknown;
          rawEvents = Array.isArray(payload)
            ? payload
            : payload &&
                typeof payload === "object" &&
                Array.isArray((payload as { events?: unknown[] }).events)
              ? (payload as { events: unknown[] }).events
              : [];
        }
      } catch {
        rawEvents = [];
      }

      const rebuiltStreams: Record<string, StreamBuffers> = {};
      const rebuiltEvents: NormalizedEmployerEvent[] = [];
      for (const item of rawEvents) {
        const raw = item as Record<string, unknown>;
        const phase = String(raw.phase ?? "");
        const type = String(raw.type ?? "");
        const step = String(raw.step ?? "");
        const data =
          raw.data && typeof raw.data === "object"
            ? (raw.data as Record<string, unknown>)
            : {};

        if (type === "stream_chunk") {
          const k = streamKey(phase, step);
          const cur = rebuiltStreams[k] ?? { reasoning: "", content: "" };
          const chunkType = String(data.chunk_type ?? "");
          const txt = String(data.text ?? "");
          if (chunkType === "reasoning") {
            rebuiltStreams[k] = { ...cur, reasoning: cur.reasoning + txt };
          } else if (chunkType === "content") {
            rebuiltStreams[k] = { ...cur, content: cur.content + txt };
          } else {
            rebuiltStreams[k] = cur;
          }
          continue;
        }

        rebuiltEvents.push({
          id: uid(),
          receivedAt: Date.now(),
          role_id: typeof raw.role_id === "string" ? raw.role_id : id,
          phase,
          type,
          step,
          message: String(raw.message ?? ""),
          model: (raw.model as string | null | undefined) ?? null,
          data,
        });
      }

      // Fallback if event history is unavailable: still hydrate key role outputs.
      if (!rebuiltEvents.length) {
        const targetSkills = Array.isArray(role.target_skills)
          ? (role.target_skills as Record<string, unknown>[])
          : [];
        const signals = Array.isArray(role.relevance_signals)
          ? (role.relevance_signals as Record<string, unknown>[])
          : [];

        rebuiltEvents.push(
          {
            id: uid(),
            receivedAt: Date.now(),
            role_id: id,
            phase: "jd_extraction",
            type: "result",
            step: "llm_extraction_done",
            message: `Loaded ${targetSkills.length} skills from saved role`,
            model: null,
            data: { raw_count: targetSkills.length, skills: targetSkills },
          },
          {
            id: uid(),
            receivedAt: Date.now(),
            role_id: id,
            phase: "team_context",
            type: "result",
            step: "team_analysis_done",
            message: `Loaded ${signals.length} team relevance signals`,
            model: null,
            data: { reasoning: "Loaded from persisted role data", signals },
          },
          {
            id: uid(),
            receivedAt: Date.now(),
            role_id: id,
            phase: "mastery",
            type: "result",
            step: "mastery_matrix_done",
            message: "Loaded saved mastery matrix",
            model: null,
            data: {
              seniority: String(role.seniority ?? ""),
              skills: targetSkills.map((s) => ({
                skill_name: String(s.skill_name ?? ""),
                tier: String(s.priority_tier ?? ""),
                team_recency:
                  signals.find(
                    (x) =>
                      String(x.skill_name ?? "").toLowerCase() ===
                      String(s.skill_name ?? "").toLowerCase()
                  )?.recency_category ?? "",
                target_mastery: Number(s.target_mastery ?? 0),
              })),
            },
          },
          {
            id: uid(),
            receivedAt: Date.now(),
            role_id: id,
            phase: "db",
            type: "complete",
            step: "db_persist_done",
            message: "Loaded historical role snapshot",
            model: null,
            data: { total_skills: targetSkills.length },
          }
        );
      }

      setStreams(rebuiltStreams);
      setEvents(rebuiltEvents);
      setPipelineDone(
        rebuiltEvents.some((e) => e.phase === "db" && e.type === "complete") ||
          String(role.status ?? "").toLowerCase() === "completed"
      );
      setSubmitState("done");
      setHistoricalMode(true);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Failed to load role history");
      setSubmitState("error");
      setHistoricalMode(false);
    } finally {
      setHistoricalLoading(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const resetAll = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setEvents([]);
    setStreams({});
    setRoleId(null);
    setWsStatus("idle");
    setSubmitError(null);
    setSubmitState("idle");
    setPipelineDone(false);
    setHistoricalData(null);
    setHistoricalLoading(false);
    setHistoricalMode(false);
    setLayoutFocus("balanced");
    setResetVersion((v) => v + 1);
  }, []);

  return {
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
    disconnect,
  };
}
