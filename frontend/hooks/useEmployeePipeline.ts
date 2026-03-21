"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { NormalizedEmployeeEvent } from "@/lib/employeeTypes";
import { employeeWsUrl } from "@/lib/config";
import type { LayoutFocus } from "./useEmployerPipeline";
import type { StreamBuffers } from "./useEmployerPipeline";

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useEmployeePipeline(
  roleId: string | null,
  setLayoutFocus: (f: LayoutFocus) => void
) {
  const [events, setEvents] = useState<NormalizedEmployeeEvent[]>([]);
  const [streams, setStreams] = useState<Record<string, StreamBuffers>>({});
  const [employeeId, setEmployeeId] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<
    "idle" | "connecting" | "open" | "closed" | "error"
  >("idle");
  const [pipelineDone, setPipelineDone] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const orchestrationScrollRef = useRef<HTMLDivElement>(null);
  const prevRoleIdRef = useRef<string | null | undefined>(undefined);

  const streamKey = useCallback(
    (phase: string, step: string) => `${phase}::${step}`,
    []
  );

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
    [streamKey]
  );

  const clearSession = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setWsStatus("idle");
    setEvents([]);
    setStreams({});
    setEmployeeId(null);
    setPipelineDone(false);
  }, []);

  useEffect(() => {
    if (prevRoleIdRef.current === undefined) {
      prevRoleIdRef.current = roleId;
      return;
    }
    if (prevRoleIdRef.current !== roleId) {
      prevRoleIdRef.current = roleId;
      clearSession();
    }
  }, [roleId, clearSession]);

  const connect = useCallback(
    (rid: string) => {
      wsRef.current?.close();
      wsRef.current = null;
      setEvents([]);
      setStreams({});
      setPipelineDone(false);
      setEmployeeId(rid);
      setWsStatus("connecting");
      setLayoutFocus("resume");

      const socket = new WebSocket(employeeWsUrl(rid));
      wsRef.current = socket;

      socket.onopen = () => {
        setWsStatus("open");
        setLayoutFocus("resume");
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

          const normalized: NormalizedEmployeeEvent = {
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

          if (
            phase === "resume_extraction" ||
            phase === "normalization" ||
            phase === "mastery" ||
            phase === "gap"
          ) {
            setLayoutFocus("resume");
          }
          if (phase === "db" && type === "complete") {
            setPipelineDone(true);
            setLayoutFocus("resume");
          }
        } catch {
          /* ignore malformed */
        }
      };

      socket.onerror = () => {
        setWsStatus("error");
      };

      socket.onclose = () => {
        setWsStatus((s) => (s === "connecting" ? "error" : "closed"));
        wsRef.current = null;
      };
    },
    [appendStream, setLayoutFocus]
  );

  const employeeBusy = wsStatus === "connecting" || wsStatus === "open";

  return {
    events,
    streams,
    streamKey,
    employeeId,
    wsStatus,
    pipelineDone,
    employeeBusy,
    connect,
    orchestrationScrollRef,
  };
}
