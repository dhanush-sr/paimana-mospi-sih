# India state/UT map — drop-in component

Self-contained choropleth of India's **28 states + 8 union territories**, shaded by
any PAIMANA state metric. No map library, no tiles, no network at runtime.

## Files

| file | what it is |
|---|---|
| `IndiaRiskMap.jsx` | the component (`"use client"`, React 19 / Tailwind v4 friendly) |
| `india-geo.json` | precomputed SVG paths + State/UT classification, 0.26 MB |
| `state_metrics.json` | per-state metrics (copy from `geo/`) |

## Usage

```jsx
import IndiaRiskMap, { METRICS } from "@/components/map/IndiaRiskMap";
import metricsFile from "@/data/state_metrics.json";

const [metric, setMetric] = useState("projects");
const [state, setState] = useState(null);

<IndiaRiskMap
  metrics={metricsFile.states}
  metricKey={metric}
  selected={state}
  onSelect={setState}
/>
```

`METRICS` is exported so the metric switcher can be rendered in the host UI rather
than baked into the map.

## Theming

Reads six CSS variables, each with a fallback, so it renders correctly even if none
are defined:

```css
--map-surface  --map-line  --map-ink  --map-ink2  --map-stroke  --map-null
```

Set the dark values under both `@media (prefers-color-scheme: dark)` and
`[data-theme="dark"]` so a theme toggle wins in both directions.

## Why there is no map library

Leaflet, Mapbox GL and MapLibre all render a **basemap from OSM/Mapbox tiles**, and
those tiles draw the India–Pakistan and India–China boundaries per *international*
convention — not India's official depiction. In a submission to MoSPI that is
disqualifying, and it would silently override the boundary work this data rests on.

Three further consequences, all in our favour:

- **Renders offline.** SIH demo wifi is unreliable; tiles fail, inline SVG cannot.
- **Zero new dependencies**, so it cannot break the Next.js build or collide with
  React 19 / Tailwind v4 versions.
- **The geometry is static** — projecting once at build time beats shipping a
  projection library that recomputes it on every page load.

## Boundary provenance — read before changing the geometry

Every off-the-shelf "India states" file tested is administratively **out of date**:

| source | features | problem |
|---|---|---|
| `survey-of-india/India-States` | 36 | no Ladakh; DNH and Daman & Diu separate |
| `survey-of-india/state-boundary` | 37 | no Ladakh; projected CRS (metres) |
| `datameet/states.geojson` | 36 | no Ladakh |

All predate the **31 Oct 2019** bifurcation of Jammu & Kashmir and the
**26 Jan 2020** merger of Dadra & Nagar Haveli with Daman & Diu.

They are, however, correct on the part that is hardest to fix: the northern frontier
reaches **37.078 N**, i.e. India's claimed boundary rather than the Line of Control.
International sources truncate near 35.5 N.

So the pipeline keeps Survey of India geometry and repairs the divisions:

```
Ladakh          = Leh (ladakh) + Kargil          (Census district geometry)
Jammu & Kashmir = SoI J&K polygon minus Ladakh   (keeps the full claimed extent,
                                                  incl. the "Data Not Available"
                                                  area the district layer omits)
DNH & DD        = Dadara & Nagar Havelli + Daman & Diu
```

### Verification gates (all must pass before the file is written)

`geo/build_india_geo.py` refuses to emit anything unless:

1. **36 features**, names matching MoSPI's `GetStateList` **exactly** (36/36)
2. **Jammu & Kashmir and Ladakh both present**, as separate entities
3. **Northern extent ≥ 36.5 N** — catches a file truncated at the LoC
4. **Zero invalid geometries**
5. Coordinates are lon/lat degrees, not a projected grid

Current run: 36 features, 36/36 names, **37.078 N**, 0 invalid. Rendered and
inspected visually as well — numeric checks cannot catch a broken projection.

## Regenerating

```bash
python geo/build_india_geo.py       # fetch + verify boundaries
python geo/build_state_metrics.py   # metrics from the harvested panel
python geo/build_map_page.py        # standalone HTML for inspection
```

## Caveat that must stay visible in the UI

State counts **sum to more than the national total**: 9.2% of projects are
multi-state corridors, counted in every state they touch. Collapsing a
Delhi–Meerut corridor into one state is exactly the distortion a map should fix, so
the double-count is deliberate — but never sum the state column to get a national
figure. `state_metrics.json → meta.overlap_note` carries this text; render it.
