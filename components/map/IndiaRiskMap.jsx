"use client";

/**
 * IndiaRiskMap - state/UT choropleth for PAIMANA.
 *
 * Deliberately has NO map-library dependency. Leaflet, Mapbox GL and MapLibre all
 * render a basemap from OSM/Mapbox tiles, which draw the India-Pakistan and
 * India-China boundaries per international convention - not India's official
 * depiction. For a submission to a Government of India ministry that is
 * disqualifying, and it would silently override the boundary work this data is
 * built on. Paths are precomputed from Survey of India geometry into
 * `india-geo.json` and rendered as inline SVG, so:
 *
 *   - the boundary shown is the one we verified (37.078 N, J&K + Ladakh split)
 *   - it renders with no network access, which matters on demo wifi
 *   - nothing is added to the dependency tree that could break the Next build
 *
 * Geometry provenance: Survey of India state outlines, with J&K bifurcated into
 * Jammu & Kashmir and Ladakh using Census district boundaries (Ladakh = Leh +
 * Kargil) and Dadra & Nagar Haveli merged with Daman & Diu. Verified: 36
 * features (28 states + 8 UTs) matching MoSPI's GetStateList exactly.
 *
 * Colours follow the project's sequential blue ramp; dark steps are selected for
 * the dark surface rather than inverted.
 */

import { useMemo, useState, useId } from "react";
import GEO from "./india-geo.json";

/** Sequential single-hue ramp, light -> dark. Magnitude only, never identity. */
const RAMP = [
  "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
  "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
];

const inr = (n) =>
  "₹" + Math.round(n).toLocaleString("en-IN");

export const METRICS = [
  { key: "projects", label: "Projects", format: (v) => v.toLocaleString("en-IN") },
  { key: "cost_cr", label: "Exposure", format: (v) => inr(v) + " cr" },
  { key: "delayed_pct", label: "% behind schedule", format: (v) => (v == null ? "—" : v.toFixed(1) + "%") },
  { key: "newly_slipped", label: "Slipped last month", format: (v) => v.toLocaleString("en-IN") },
  { key: "median_delay_months", label: "Median delay", format: (v) => (v == null ? "—" : v.toFixed(1) + " mo") },
];

/**
 * @param {object}   metrics   state name -> metric object (from state_metrics.json)
 * @param {string}   metricKey which metric to shade by
 * @param {string?}  selected  currently selected state name
 * @param {function} onSelect  (stateName|null) => void
 */
export default function IndiaRiskMap({
  metrics = {},
  metricKey = "projects",
  selected = null,
  onSelect = () => {},
  className = "",
}) {
  const [hover, setHover] = useState(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const titleId = useId();

  const metric = METRICS.find((m) => m.key === metricKey) || METRICS[0];

  const scale = useMemo(() => {
    const vals = Object.keys(GEO.states)
      .map((s) => metrics[s]?.[metric.key])
      .filter((v) => v != null && !Number.isNaN(v));
    if (!vals.length) return { lo: 0, hi: 1 };
    return { lo: Math.min(...vals), hi: Math.max(...vals) };
  }, [metrics, metric.key]);

  const colorFor = (v) => {
    if (v == null || Number.isNaN(v)) return "var(--map-null, #ececea)";
    const t = scale.hi === scale.lo ? 0.5 : (v - scale.lo) / (scale.hi - scale.lo);
    return RAMP[Math.max(0, Math.min(RAMP.length - 1, Math.round(t * (RAMP.length - 1))))];
  };

  const entries = Object.entries(GEO.states);
  const active = hover || selected;
  const activeMetrics = active ? metrics[active] : null;

  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox={GEO.viewBox}
        role="img"
        aria-labelledby={titleId}
        className="w-full h-auto select-none"
        onMouseLeave={() => setHover(null)}
      >
        <title id={titleId}>
          Choropleth of India&apos;s 28 states and 8 union territories, shaded by {metric.label.toLowerCase()}
        </title>
        {entries.map(([name, { d, kind }]) => {
          const v = metrics[name]?.[metric.key];
          const isSel = selected === name;
          return (
            <path
              key={name}
              d={d}
              fill={colorFor(v)}
              tabIndex={0}
              role="button"
              aria-label={`${name}, ${kind}: ${v == null ? "no data" : metric.format(v)}`}
              className="cursor-pointer outline-none transition-opacity hover:opacity-80 focus-visible:opacity-80"
              stroke={isSel ? "var(--map-ink, #0b0b0b)" : "var(--map-stroke, #fcfcfb)"}
              strokeWidth={isSel ? 1.6 : 0.6}
              onMouseEnter={() => setHover(name)}
              onMouseMove={(e) => setPointer({ x: e.clientX, y: e.clientY })}
              onFocus={() => setHover(name)}
              onBlur={() => setHover(null)}
              onClick={() => onSelect(isSel ? null : name)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(isSel ? null : name);
                }
              }}
            />
          );
        })}
      </svg>

      {/* Legend - always present; a sequential scale is unreadable without one. */}
      <div className="mt-2 flex items-center gap-2 text-[11.5px] text-[var(--map-ink2,#52514e)]">
        <span className="tabular-nums">{metric.format(scale.lo)}</span>
        <span className="flex h-[11px] flex-1 overflow-hidden rounded-[3px]">
          {RAMP.map((c) => (
            <i key={c} className="flex-1" style={{ background: c }} />
          ))}
        </span>
        <span className="tabular-nums">{metric.format(scale.hi)}</span>
      </div>

      {active && activeMetrics && (
        <div
          role="status"
          aria-live="polite"
          className="pointer-events-none fixed z-50 max-w-[270px] rounded-[9px] border
                     border-[var(--map-line,#e3e3df)] bg-[var(--map-surface,#fcfcfb)]
                     px-3 py-2 text-[12.5px] shadow-lg"
          style={{
            left: Math.min(pointer.x + 14, (typeof window !== "undefined" ? window.innerWidth : 1200) - 290),
            top: Math.max(10, pointer.y - 150),
          }}
        >
          <b className="mb-1 block text-[13px]">{active}</b>
          <Row label={GEO.states[active]?.kind} value="" />
          <Row label="Projects" value={activeMetrics.projects?.toLocaleString("en-IN")} />
          <Row label="Exposure" value={inr(activeMetrics.cost_cr) + " cr"} />
          <Row
            label="Behind schedule"
            value={activeMetrics.delayed_pct == null ? "—" : activeMetrics.delayed_pct + "%"}
          />
          <Row
            label="Median delay"
            value={
              activeMetrics.median_delay_months == null
                ? "—"
                : activeMetrics.median_delay_months + " mo"
            }
          />
          <Row label="Slipped last month" value={activeMetrics.newly_slipped} />
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4 text-[var(--map-ink2,#52514e)]">
      <span>{label}</span>
      <span className="tabular-nums text-[var(--map-ink,#0b0b0b)]">{value}</span>
    </div>
  );
}
