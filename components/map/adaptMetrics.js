/**
 * Adapters that turn either available data source into the shape IndiaRiskMap
 * expects. Written because the two sources genuinely differ, and guessing at the
 * contract at integration time is how a demo breaks on stage.
 *
 *   A. state_metrics.json  - computed offline from the harvested panel.
 *                            Richest: delay %, median delay, newly-slipped.
 *   B. GET /benchmark?by=state - the API that already exists in api.py.
 *                            Returns { grp, n, mean_risk, unspent_cr, exposure_cr }.
 *                            Has model risk, but no schedule fields.
 *
 * Neither is a superset of the other, so both are supported and the map only
 * offers the metrics the chosen source can actually populate.
 */

/** The metric keys IndiaRiskMap understands. */
export const METRIC_KEYS = [
  "projects",
  "cost_cr",
  "delayed_pct",
  "newly_slipped",
  "median_delay_months",
  "mean_risk",
  "unspent_cr",
];

/**
 * Source A: state_metrics.json -> map metrics.
 * Pass the whole parsed file; returns { states, meta }.
 */
export function fromStateMetrics(file) {
  if (!file || !file.states) {
    throw new Error("fromStateMetrics: expected the parsed state_metrics.json");
  }
  return { states: file.states, meta: file.meta || {} };
}

/**
 * Source B: GET /benchmark?by=state -> map metrics.
 *
 * The API keys states by `grp`. Names must match MoSPI's GetStateList exactly,
 * because that is what the geometry is keyed on - a silent mismatch would render
 * a state grey rather than error, so unmatched names are returned for the caller
 * to surface rather than swallowed.
 */
export function fromBenchmark(payload, knownStates) {
  const rows = Array.isArray(payload) ? payload : payload?.data || [];
  const states = {};
  const unmatched = [];
  for (const r of rows) {
    const name = r.grp ?? r.state ?? r.name;
    if (!name) continue;
    if (knownStates && !knownStates.includes(name)) {
      unmatched.push(name);
      continue;
    }
    states[name] = {
      projects: num(r.n),
      cost_cr: num(r.exposure_cr),
      unspent_cr: num(r.unspent_cr),
      mean_risk: num(r.mean_risk),
      // Not available from this endpoint - left null so the map greys them
      // rather than showing a fabricated zero.
      delayed_pct: null,
      newly_slipped: null,
      median_delay_months: null,
    };
  }
  return { states, meta: { source: "/benchmark?by=state" }, unmatched };
}

/** Which metrics a given source can actually fill, so the switcher hides the rest. */
export function availableMetrics(states) {
  const has = (k) => Object.values(states).some((v) => v?.[k] != null);
  return METRIC_KEYS.filter(has);
}

function num(v) {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}
