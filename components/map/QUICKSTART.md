# Using the India map — start here

There are three ways in. **Option 1 needs nothing installed** and is what you want if
you just came to look at the map.

---

## Option 1 — Just look at it (0 setup, works offline)

**Open this file in any browser:**

```
docs/india_map_preview.html
```

Double-click it. That's the whole procedure.

No `npm install`, no server, no Python, no internet. The map geometry and all the data
are embedded inside that one file (288 KB). It works from a USB stick on a laptop with
no wifi — which is the point, because SIH demo networks are unreliable.

You get: all 36 states and UTs, five switchable metrics, hover tooltips, click-to-select,
a ranked table, the small-UT strip, and dark mode.

> **This is the answer to "there's no frontend yet".** You do not need one.

---

## Option 2 — Put it in a React/Next app

Only needed when you want the map *inside* the dashboard rather than beside it.

**Copy two folders:**

```
components/map/IndiaRiskMap.jsx      →  your-app/components/map/
components/map/india-geo.json        →  your-app/components/map/
components/map/adaptMetrics.js       →  your-app/components/map/
components/map/state_metrics.json    →  your-app/data/
```

**Use it:**

```jsx
"use client";
import { useState } from "react";
import IndiaRiskMap, { METRICS } from "@/components/map/IndiaRiskMap";
import { fromStateMetrics } from "@/components/map/adaptMetrics";
import metricsFile from "@/data/state_metrics.json";

export default function MapPanel() {
  const { states, meta } = fromStateMetrics(metricsFile);
  const [metric, setMetric] = useState("projects");
  const [selected, setSelected] = useState(null);

  return (
    <>
      <div className="flex gap-2">
        {METRICS.map((m) => (
          <button key={m.key} onClick={() => setMetric(m.key)}
                  aria-pressed={metric === m.key}>{m.label}</button>
        ))}
      </div>

      <IndiaRiskMap
        metrics={states}
        metricKey={metric}
        selected={selected}
        onSelect={setSelected}
      />

      <p className="text-xs opacity-70">{meta.overlap_note}</p>
    </>
  );
}
```

**Nothing to install.** No Leaflet, no Mapbox, no D3 — it is inline SVG. It cannot
break your build because it adds no dependencies.

---

## Option 3 — Feed it live data from the API

Use this when you want the map to reflect the running model rather than the snapshot.

```jsx
import { fromBenchmark, availableMetrics } from "@/components/map/adaptMetrics";
import GEO from "@/components/map/india-geo.json";

const res  = await fetch("/benchmark?by=state");
const { states, unmatched } = fromBenchmark(await res.json(), Object.keys(GEO.states));

if (unmatched.length) console.warn("state names not in geometry:", unmatched);

// only offer metrics this source can actually fill
const usable = availableMetrics(states);   // ["projects","cost_cr","mean_risk","unspent_cr"]
```

**Important:** `/benchmark?by=state` has **no schedule fields** — no `delayed_pct`, no
`newly_slipped`, no `median_delay_months`. If you offer those in the switcher anyway,
the user picks one and gets a fully grey map with no explanation. Call
`availableMetrics()` and only show what the source can fill.

Also: **state names are the join key** and must match MoSPI's `GetStateList` exactly.
`"NCT of Delhi"` will silently fail to match `"Delhi"` — which is why `fromBenchmark`
returns `unmatched` rather than swallowing it. Log it.

---

## Regenerating the data

Only if the underlying panel changes:

```bash
python components/map/build/build_state_metrics.py   # recompute metrics
python components/map/build/build_map_page.py        # rebuild the standalone HTML
```

Rebuilding the geometry itself (rarely needed — India's borders do not change monthly):

```bash
python components/map/build/build_india_geo.py
```

That script **refuses to write a file** unless all five gates pass: 36 features, names
matching MoSPI exactly, northern extent ≥ 36.5 N, zero invalid geometries, lon/lat
degrees. If it fails, it tells you which gate — do not bypass it.

---

## Reading the map correctly

Two traps that will otherwise cause a wrong conclusion on stage:

1. **Nine states/UTs are too small to see** — Delhi renders at 89 px², Chandigarh at
   8 px². They hold 96 projects between them. That is what the strip under the map is
   for. **Area is not importance.**

2. **Do not sum the state column.** Counts total 2,097 against 1,775 national projects,
   because 162 projects (9.2%) are multi-state corridors counted in every state they
   touch. Deliberate — but it means the column does not add up to the national figure.
   Keep `meta.overlap_note` visible in the UI.

Full detail in `MAP_GUIDE.md`.
