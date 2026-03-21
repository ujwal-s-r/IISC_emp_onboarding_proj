"use client";

import { useCallback, useRef, useState } from "react";
import type { NormalizedEmployerEvent } from "@/lib/employerTypes";
import { employerSetupUrl as setupUrl, employerWsUrl as wsUrl } from "@/lib/config";

export type LayoutFocus = "balanced" | "employer" | "resume";

export interface StreamBuffers {
  reasoning: string;
  content: string;
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

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
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
    layoutFocus,
    setLayoutFocus,
    startAnalysis,
    disconnect,
  };
}
