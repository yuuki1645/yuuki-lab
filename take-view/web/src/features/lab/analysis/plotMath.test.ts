import { describe, expect, it } from "vitest";
import type { LabWindow } from "../types";
import {
  clampView,
  dataExtent,
  focusView,
  formatNumber,
  formatOffset,
  nearestIndex,
  niceTicks,
  panView,
  revealTime,
  timeTicks,
  valueAt,
  zoomView,
} from "./plotMath";

function rawWindow(t: number[], v: Array<number | null>): LabWindow {
  return {
    from: t[0],
    to: t[t.length - 1],
    channels: ["j0.corr"],
    sample_count: t.length,
    mode: "raw",
    t,
    index: t.map((_, i) => 100 + i),
    series: { "j0.corr": { v } },
  };
}

describe("view math", () => {
  it("keeps a view inside the take and above the minimum span", () => {
    expect(clampView({ from: -5, to: 5 }, 100)).toEqual({ from: 0, to: 10 });
    expect(clampView({ from: 95, to: 110 }, 100)).toEqual({ from: 85, to: 100 });
    expect(clampView({ from: 10, to: 10.01 }, 100).to - 10).toBeCloseTo(0.25);
    expect(clampView({ from: 0, to: 500 }, 100)).toEqual({ from: 0, to: 100 });
  });

  it("zooms around the point under the mouse", () => {
    const next = zoomView({ from: 0, to: 100 }, 25, 0.5, 1000);
    expect(next.to - next.from).toBeCloseTo(50);
    // 25 was a quarter of the way in and stays a quarter of the way in.
    expect((25 - next.from) / (next.to - next.from)).toBeCloseTo(0.25);
  });

  it("pans without changing the span and stops at the ends", () => {
    expect(panView({ from: 10, to: 20 }, 5, 100)).toEqual({ from: 15, to: 25 });
    expect(panView({ from: 90, to: 100 }, 5, 100)).toEqual({ from: 90, to: 100 });
  });

  it("frames a short anomaly with context on both sides", () => {
    const view = focusView(50, 50.05, 1000);
    expect(view.from).toBeLessThan(50);
    expect(view.to).toBeGreaterThan(50.05);
    expect(view.to - view.from).toBeGreaterThanOrEqual(4);
  });

  it("only moves the view when the time is off screen", () => {
    const view = { from: 10, to: 20 };
    expect(revealTime(view, 15, 100)).toBe(view);
    expect(revealTime(view, 40, 100)).toEqual({ from: 35, to: 45 });
  });
});

describe("ticks and text", () => {
  it("places time ticks on round steps", () => {
    const { step, ticks } = timeTicks({ from: 0.3, to: 10.2 }, 5);
    expect(step).toBe(2);
    expect(ticks).toEqual([2, 4, 6, 8, 10]);
  });

  it("places value ticks on 1 / 2 / 5 steps", () => {
    expect(niceTicks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10]);
    expect(niceTicks(-0.3, 0.3, 3)).toEqual([-0.2, 0, 0.2]);
  });

  it("formats offsets as m:ss with decimals for short steps", () => {
    expect(formatOffset(65)).toBe("1:05");
    expect(formatOffset(65.25, 0.1)).toBe("1:05.3");
    expect(formatOffset(59.96, 0.5)).toBe("1:00.0");
    expect(formatOffset(3725, 1)).toBe("1:02:05");
  });

  it("never prints a gap as zero", () => {
    expect(formatNumber(null)).toBe("\u2014");
    expect(formatNumber(Number.NaN)).toBe("\u2014");
    expect(formatNumber(0, 2)).toBe("0.00");
    expect(formatNumber(1499994, 3)).toBe("1499994");
  });
});

describe("window lookups", () => {
  it("finds the nearest sample", () => {
    expect(nearestIndex([0, 1, 2, 3], 2.4)).toBe(2);
    expect(nearestIndex([0, 1, 2, 3], 2.6)).toBe(3);
    expect(nearestIndex([], 1)).toBe(-1);
  });

  it("reads the value at a time and keeps gaps as null", () => {
    const data = rawWindow([0, 0.05, 0.1, 0.15], [1, null, 3, 4]);
    expect(valueAt(data, "j0.corr", 0.11)?.value).toBe(3);
    expect(valueAt(data, "j0.corr", 0.11)?.index).toBe(102);
    expect(valueAt(data, "j0.corr", 0.05)?.value).toBeNull();
    // Far outside the loaded rows there is no answer at all.
    expect(valueAt(data, "j0.corr", 5)).toBeNull();
  });

  it("measures the extent inside the view only, envelope by min/max", () => {
    const raw = rawWindow([0, 1, 2, 3], [5, 1, 9, -4]);
    expect(dataExtent(raw, ["j0.corr"], { from: 0.5, to: 2.5 })).toEqual([1, 9]);
    const envelope: LabWindow = {
      ...raw,
      mode: "envelope",
      bucket_sec: 1,
      series: { "j0.corr": { min: [0, -2, null, 1], max: [2, 7, null, 3], mean: [1, 2, null, 2] } },
    };
    expect(dataExtent(envelope, ["j0.corr"], { from: 0, to: 3 })).toEqual([-2, 7]);
  });
});
