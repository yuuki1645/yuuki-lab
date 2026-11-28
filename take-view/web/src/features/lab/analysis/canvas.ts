/** Small canvas helpers shared by the plot and the health map. */

import { useLayoutEffect, useState, type RefObject } from "react";

/** Solid colour per severity (1 info, 2 warn, 3 crit). */
export const SEV_COLOR: Record<number, string> = {
  1: "#7f8ea3",
  2: "#ffb020",
  3: "#ff5c5c",
};

/** Translucent fill per severity for background bands behind data. */
export const SEV_FILL: Record<number, string> = {
  1: "rgba(127, 142, 163, 0.10)",
  2: "rgba(255, 176, 32, 0.14)",
  3: "rgba(255, 92, 92, 0.20)",
};

/** Ten distinguishable colours, one per logical axis. */
export const JOINT_COLORS: readonly string[] = [
  "#4da6ff",
  "#ffb454",
  "#7dcea0",
  "#ff7a7a",
  "#b48ef0",
  "#5ad1d1",
  "#f0d05a",
  "#f08ac8",
  "#9ad15a",
  "#c8d0da",
];

export const MONO_FONT = '11px ui-monospace, "Cascadia Code", Consolas, monospace';
export const LABEL_FONT = '11px "Inter", "Noto Sans JP", "Meiryo", sans-serif';

export type Theme = { grid: string; text: string; muted: string; accent: string; surface: string; bg: string };

let cachedTheme: Theme | null = null;

/** CSS custom properties from tokens.css, read once. */
export function readTheme(): Theme {
  if (cachedTheme) return cachedTheme;
  const style = getComputedStyle(document.documentElement);
  const pick = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  cachedTheme = {
    grid: pick("--border", "#2d3f56"),
    text: pick("--text", "#e8edf4"),
    muted: pick("--text-muted", "#9aadc4"),
    accent: pick("--accent", "#4da6ff"),
    surface: pick("--surface", "#1a2332"),
    bg: pick("--bg", "#0f1419"),
  };
  return cachedTheme;
}

/**
 * Size a canvas for the device pixel ratio and return a cleared context
 * whose units are CSS pixels. Keeps lines crisp on high-DPI screens.
 */
export function setupCanvas(canvas: HTMLCanvasElement, width: number, height: number): CanvasRenderingContext2D | null {
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  const pixelWidth = Math.max(1, Math.round(width * ratio));
  const pixelHeight = Math.max(1, Math.round(height * ratio));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return ctx;
}

/** Content width of an element, kept in sync with a ResizeObserver. */
export function useElementWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    setWidth(Math.floor(node.getBoundingClientRect().width));
    const observer = new ResizeObserver((entries) => {
      const next = Math.floor(entries[0]?.contentRect.width ?? 0);
      // Ignore sub-pixel jitter so a scrollbar flicker does not redraw everything.
      setWidth((prev) => (Math.abs(prev - next) >= 1 ? next : prev));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
