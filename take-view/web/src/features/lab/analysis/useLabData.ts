/**
 * Data hooks for the workbench. Each one debounces, cancels the previous
 * request when its inputs change, and keeps showing the last result until
 * the new one arrives, so zooming never flashes an empty plot.
 */

import { useEffect, useState } from "react";
import { labApi } from "../api";
import { isAbort } from "../errors";
import type { LabRangeStats, LabRows, LabSample, LabWindow } from "../types";
import { pointsForWidth, type View } from "./plotMath";

/** Plot data for the view, fetched with a margin so small pans stay filled. */
export function useWindowData(
  day: string,
  takeId: string,
  channels: string[],
  view: View | null,
  width: number,
  side: string | null = null
) {
  const [data, setData] = useState<LabWindow | null>(null);
  const [loading, setLoading] = useState(false);
  const key = channels.join(",");
  const from = view?.from;
  const to = view?.to;

  useEffect(() => {
    if (from == null || to == null || !key || width <= 0) return;
    const ctrl = new AbortController();
    const span = to - from;
    // A quarter span either side: panning a little reuses what is loaded
    // while the next request is in flight.
    const start = Math.max(0, from - span * 0.25);
    const end = to + span * 0.25;
    const points = Math.round(pointsForWidth(width) * 1.5);
    const timer = window.setTimeout(() => {
      setLoading(true);
      labApi
        .getWindow(day, takeId, key.split(","), start, end, points, ctrl.signal, side)
        .then((body) => setData(body))
        .catch((err: unknown) => {
          if (!isAbort(err)) setData(null);
        })
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, 80);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [day, takeId, key, from, to, width, side]);

  return { data, loading };
}

/** Descriptive stats of the visible range. Slower debounce: not needed per frame. */
export function useRangeStats(
  day: string,
  takeId: string,
  channels: string[],
  view: View | null,
  side: string | null = null
) {
  const [stats, setStats] = useState<LabRangeStats | null>(null);
  const [loading, setLoading] = useState(false);
  const key = channels.join(",");
  const from = view?.from;
  const to = view?.to;

  useEffect(() => {
    if (from == null || to == null || !key) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      labApi
        .getStats(day, takeId, key.split(","), from, to, ctrl.signal, side)
        .then((body) => setStats(body))
        .catch(() => undefined)
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [day, takeId, key, from, to, side]);

  return { stats, loading };
}

/** Recorded rows from a start index, for the data table. */
export function useRows(
  day: string,
  takeId: string,
  channels: string[],
  start: number | null,
  count: number,
  side: string | null = null
) {
  const [rows, setRows] = useState<LabRows | null>(null);
  const [loading, setLoading] = useState(false);
  const key = channels.join(",");

  useEffect(() => {
    if (start == null || !key) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      setLoading(true);
      labApi
        .getRows(day, takeId, key.split(","), start, count, ctrl.signal, side)
        .then((body) => setRows(body))
        .catch(() => undefined)
        .finally(() => {
          if (!ctrl.signal.aborted) setLoading(false);
        });
    }, 60);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
  }, [day, takeId, key, start, count, side]);

  return { rows, loading };
}

/** A request for one row: by index, or nearest to an offset. */
export type SampleRequest = { index?: number; t?: number; nonce: number };

/** The picked row, exactly as recorded. */
export function useSample(day: string, takeId: string, request: SampleRequest | null, side: string | null = null) {
  const [sample, setSample] = useState<LabSample | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    setLoading(true);
    labApi
      .getSample(day, takeId, { index: request.index, t: request.t }, ctrl.signal, side)
      .then((body) => setSample(body))
      .catch(() => undefined)
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [day, takeId, request, side]);

  return { sample, loading };
}
