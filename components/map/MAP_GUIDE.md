# The India map — how to read it, and how to wire it in

For the PAIMANA team (SIH 2026, PS 26103). Two halves: **reading it** (anyone) and
**integrating it** (whoever owns the UI).

---

# Part 1 — Reading the map

## What it shows

One shaded polygon per **state or union territory**, coloured by whichever metric is
selected. Darker = higher. It answers *"where is the delivery risk concentrated?"* —
the question a table of 1,775 project rows cannot answer at a glance.

## The five metrics

| metric | what it means | read it as |
|---|---|---|
| **Projects** | count of monitored projects touching that state | portfolio weight |
| **Exposure** | sum of original approved cost, ₹ crore | money at stake |
| **% behind schedule** | share whose revised date is later than the original | *chronic* trouble |
| **Slipped last month** | date moved between the last two snapshots | *fresh* trouble |
| **Median delay** | typical slippage in months | severity |

**"% behind schedule" and "Slipped last month" are different questions.** The first is
a standing condition; the second is what changed this month. A state can be 85% behind
schedule and have nothing slip last month — that is a stable problem, not an emerging
one. For escalation, the second is usually more actionable.

## The strip below the map — read this before you conclude anything

Nine of the 36 are **too small to see on a geographic map**:

| | rendered size | projects |
|---|---:|---:|
| Chandigarh | 8 px² | 3 |
| Puducherry | 24 px² | 9 |
| Lakshadweep | 27 px² | 2 |
| Dadra & NH and Daman & Diu | 30 px² | 7 |
| **Delhi** | **89 px²** | **19** |
| Goa | 179 px² | 9 |
| Andaman & Nicobar | 349 px² | 9 |
| Sikkim | 416 px² | 21 |
| Tripura | 568 px² | 17 |

Together they hold **96 projects**, and Delhi — the national capital — is a speck.
They are still on the map; the strip is **additional**, not a replacement.

**This is the single most important thing to understand about any choropleth: area is
not importance.** Rajasthan looks enormous and holds 74 projects. Delhi is invisible
and holds 19. Never read "big and dark" as "biggest problem".

## The overlap warning — do not sum the column

State counts sum to **2,097** against **1,775** national projects, because **162
projects (9.2%) are multi-state corridors** counted in every state they touch.

That is deliberate. A Delhi–Meerut RRTS corridor genuinely *is* a Delhi project and a
UP project; collapsing it into one is exactly the distortion a map should fix. But it
means **summing the state column double-counts**. The note under the map says this;
keep it visible.

## Interactions

| action | effect |
|---|---|
| hover a state or tile | tooltip with all five metrics |
| click | select / deselect; syncs with the ranked table |
| `Tab` / `Enter` | full keyboard access — every state is a focusable button |
| ranked table | the accessible alternative to colour; also click-to-select |

## What it is NOT

- **Not predictive.** These are current and historical facts. Model output is a
  separate concern.
- **Not a basemap.** There are no roads, cities or terrain, by design — see Part 2.
- **Not project locations.** A project is attributed to whole states, not plotted at a
  point. There are no coordinates in the feed.

---

# Part 2 — Integration

## Files

```
IndiaRiskMap.jsx      the component ("use client")
india-geo.json        precomputed SVG paths + State/UT flags (0.26 MB)
adaptMetrics.js       converts either data source into the expected shape
state_metrics.json    offline-computed metrics (richest source)
```

## Wiring it up

```jsx
import IndiaRiskMap, { METRICS } from "@/components/map/IndiaRiskMap";
import { fromStateMetrics } from "@/components/map/adaptMetrics";
import metricsFile from "@/data/state_metrics.json";

const { states, meta } = fromStateMetrics(metricsFile);
const [metric, setMetric] = useState("projects");
const [selected, setSelected] = useState(null);

<IndiaRiskMap
  metrics={states}
  metricKey={metric}
  selected={selected}
  onSelect={setSelected}
/>
<p className="note">{meta.overlap_note}</p>   {/* keep this visible */}
```

## Two data sources, and they are NOT interchangeable

| | `state_metrics.json` | `GET /benchmark?by=state` |
|---|---|---|
| projects | ✅ | ✅ (`n`) |
| exposure | ✅ | ✅ (`exposure_cr`) |
| % behind schedule | ✅ | ❌ |
| slipped last month | ✅ | ❌ |
| median delay | ✅ | ❌ |
| model risk | ❌ | ✅ (`mean_risk`) |
| unspent | ❌ | ✅ (`unspent_cr`) |

Neither is a superset. Use `fromBenchmark()` for the live API, and call
`availableMetrics()` so the switcher only offers metrics that source can fill —
otherwise a user picks "median delay" and gets a fully grey map with no explanation.

```jsx
import { fromBenchmark, availableMetrics } from "./adaptMetrics";
const { states, unmatched } = fromBenchmark(await res.json(), Object.keys(GEO.states));
if (unmatched.length) console.warn("states not in geometry:", unmatched);
```

**Names are the join key.** They must match MoSPI's `GetStateList` exactly. A mismatch
renders that state grey rather than throwing — which is why `fromBenchmark` returns
`unmatched` instead of swallowing it. Check it.

## Theming

Six CSS variables, all with fallbacks:

```css
--map-surface  --map-line  --map-ink  --map-ink2  --map-stroke  --map-null
```

Define the dark values under **both** `@media (prefers-color-scheme: dark)` and
`[data-theme="dark"]` so a manual toggle wins in both directions.

## Why there is no Leaflet / Mapbox

They render basemap **tiles**, and those tiles draw the India–Pakistan and India–China
boundaries per *international* convention — **not India's official depiction**. In a
submission to MoSPI that is disqualifying, and it would silently override the boundary
work the geometry rests on.

Consequences, all favourable: renders with **no network**, adds **zero dependencies**
(so it cannot break the Next.js build or collide with React 19 / Tailwind v4), and the
projection is computed once at build time rather than in every browser.

## Boundary provenance

Survey of India geometry, with administrative divisions repaired from Census districts:

```
Ladakh          = Leh (ladakh) + Kargil
Jammu & Kashmir = SoI J&K polygon minus Ladakh   (keeps the full claimed extent)
DNH & DD        = Dadara & Nagar Havelli + Daman & Diu
```

Necessary because **every** off-the-shelf file tested is administratively stale — no
Ladakh, DNH still separate — all predating Oct 2019 and Jan 2020. They are correct on
the hard part: the northern frontier reaches **37.078 N**, India's claimed boundary,
where international sources truncate near 35.5 N.

`build_india_geo.py` refuses to emit a file unless all five gates pass:

1. 36 features · 2. names matching MoSPI exactly (36/36) · 3. northern extent ≥ 36.5 N ·
4. zero invalid geometries · 5. coordinates in lon/lat degrees

## Regenerating

```bash
python geo/build_india_geo.py       # fetch + verify boundaries
python geo/build_state_metrics.py   # recompute metrics from the panel
python geo/build_map_page.py        # standalone HTML for inspection
```

Open `geo/india_map.html` to check a change without running the app.

## Known limitations

- **Not verified inside the Next.js app.** The `ui/` directory is committed as a broken
  gitlink (no `.gitmodules`, pointing at a commit that does not exist), so a clone gets
  an empty folder. The component was verified standalone. **Re-check it once the UI is
  actually committed.**
- Multi-state corridors are counted in each state; the map does not yet *draw* the
  corridor links.
- Colour alone does not separate the small UTs — they cluster at the bottom of the
  scale — which is why the tiles carry printed values.
