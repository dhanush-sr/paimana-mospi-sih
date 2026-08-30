# -*- coding: utf-8 -*-
"""Build a CURRENT, verified India state/UT boundary GeoJSON for the PAIMANA map.

Why this is not a one-line download
-----------------------------------
Every ready-made "India states" file tested is administratively out of date:

  survey-of-india/India-States      36 features, no Ladakh, DNH and Daman & Diu separate
  survey-of-india/state-boundary    37 features, no Ladakh, projected CRS (metres)
  datameet/states.geojson           36 features, no Ladakh

They all predate the 31 Oct 2019 bifurcation of Jammu & Kashmir and the
26 Jan 2020 merger of Dadra & Nagar Haveli with Daman & Diu. Shipping any of
them to MoSPI would show a map of India that is six years stale.

They are, however, correct on the thing that matters most and is hardest to fix:
the **northern frontier reaches 37.08 N**, i.e. India's claimed boundary rather
than the Line of Control. International sources (Natural Earth, OSM defaults)
truncate near 35.5 N, which is not India's official depiction and is not
publishable in a Government of India context.

So: keep the Survey of India geometry, and repair the administrative divisions
from the Census district file, which still carries Leh and Kargil as districts.

  Ladakh          = Leh (ladakh) + Kargil
  Jammu & Kashmir = the remaining J&K districts, including the
                    "Data Not Available" polygon that carries the
                    PoK / Aksai Chin extent India claims - it must NOT be dropped
  DNH & DD        = Dadara & Nagar Havelli + Daman & Diu

Output is verified against MoSPI's own GetStateList before it is written.
"""
import io
import json
import os
import ssl
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import shapefile
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from shapely.validation import make_valid

HERE = os.path.dirname(os.path.abspath(__file__))
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 research/1.0"}
BASE = "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main/data/survey-of-india"

# MoSPI GetStateList - the exact 36 names the app joins on.
MOSPI = ["Andaman & Nicobar", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar",
         "Chandigarh", "Chhattisgarh", "Dadra & Nagar Haveli and Daman & Diu", "Delhi",
         "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand",
         "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh", "Maharashtra",
         "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab",
         "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh",
         "Uttarakhand", "West Bengal"]

# Survey of India spelling -> MoSPI spelling
RENAME = {
    "Andaman & Nicobar Island": "Andaman & Nicobar",
    "Arunanchal Pradesh": "Arunachal Pradesh",
    "NCT of Delhi": "Delhi",
}
MERGE_DNHDD = {"Dadara & Nagar Havelli", "Daman & Diu"}
LADAKH_DISTRICTS = {"leh (ladakh)", "kargil"}


def get(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=300, context=CTX).read()


def read_shp(stem):
    parts = {}
    for ext in ("shp", "dbf", "shx"):
        try:
            parts[ext] = get(f"{stem}.{ext}")
        except Exception:
            pass
    r = shapefile.Reader(shp=io.BytesIO(parts["shp"]), dbf=io.BytesIO(parts["dbf"]),
                         shx=io.BytesIO(parts["shx"]) if parts.get("shx") else None)
    fields = [f[0] for f in r.fields[1:]]
    out = []
    for sr in r.shapeRecords():
        out.append((dict(zip(fields, list(sr.record))), sr.shape.__geo_interface__))
    return out


def clean(geom):
    g = shape(geom)
    if not g.is_valid:
        g = make_valid(g)
    return g


print("downloading Survey of India state boundaries ...", flush=True)
states = read_shp(f"{BASE}/India-States")
print(f"  {len(states)} state features")

print("downloading Census district boundaries ...", flush=True)
districts = read_shp(f"{BASE}/India-Districts-2011Census")
print(f"  {len(districts)} district features")

# ---- CRS sanity: these must be lon/lat degrees, not a projected grid ----
xs = []
for _, g in states:
    def walk(c):
        if isinstance(c, (list, tuple)):
            if c and isinstance(c[0], (int, float)):
                xs.append(c[0])
            else:
                for i in c:
                    walk(i)
    walk(g.get("coordinates", []))
if not (60 <= min(xs) <= 100 and 60 <= max(xs) <= 100):
    sys.exit(f"ABORT: coordinates are not lon/lat degrees (x range {min(xs):.1f}..{max(xs):.1f}). "
             "A projected CRS would need reprojection before use.")
print(f"  CRS check OK - longitudes {min(xs):.2f}..{max(xs):.2f} (degrees)")

# ---- build Ladakh and the reduced J&K from districts ----
jk_leftover, ladakh_parts = [], []
for rec, geom in districts:
    if str(rec.get("ST_NM", "")).strip().lower() != "jammu & kashmir":
        continue
    d = str(rec.get("DISTRICT", "")).strip().lower()
    (ladakh_parts if d in LADAKH_DISTRICTS else jk_leftover).append(clean(geom))

if len(ladakh_parts) != 2:
    sys.exit(f"ABORT: expected Leh + Kargil, found {len(ladakh_parts)} Ladakh districts")
print(f"  Ladakh from {len(ladakh_parts)} districts; J&K from {len(jk_leftover)} districts")

ladakh_geom = unary_union(ladakh_parts)

# The SoI J&K polygon carries the full claimed extent (incl. PoK / Aksai Chin).
# Subtracting Ladakh from THAT - rather than unioning the districts - keeps the
# claimed area, which the district layer does not fully cover.
soi_jk = None
others = []
dnhdd_parts = []
for rec, geom in states:
    nm = str(rec.get("ST_NM", "")).strip()
    if nm == "Jammu & Kashmir":
        soi_jk = clean(geom)
    elif nm in MERGE_DNHDD:
        dnhdd_parts.append(clean(geom))
    else:
        others.append((RENAME.get(nm, nm), clean(geom)))

if soi_jk is None:
    sys.exit("ABORT: Jammu & Kashmir not found in the state file")

jk_new = soi_jk.difference(ladakh_geom)
ladakh_final = soi_jk.intersection(ladakh_geom)   # keep Ladakh inside the claimed extent

feats = []


def add(name, geom):
    if geom.is_empty:
        sys.exit(f"ABORT: empty geometry for {name}")
    feats.append({"type": "Feature",
                  "properties": {"state": name},
                  "geometry": mapping(geom)})


for nm, g in others:
    add(nm, g)
add("Jammu & Kashmir", jk_new)
add("Ladakh", ladakh_final)
if dnhdd_parts:
    add("Dadra & Nagar Haveli and Daman & Diu", unary_union(dnhdd_parts))

# ---------------------------------------------------------------- verify
print("\n" + "=" * 68)
print("VERIFICATION")
print("=" * 68)
names = sorted(f["properties"]["state"] for f in feats)
want = sorted(MOSPI)
print(f"  features           : {len(feats)}  (expected 36)")
missing = [n for n in want if n not in names]
extra = [n for n in names if n not in want]
print(f"  exact name matches : {len(set(names) & set(want))}/36")
if missing:
    print(f"  MISSING            : {missing}")
if extra:
    print(f"  UNEXPECTED         : {extra}")

lat_max = -90
lon_min, lon_max = 200, -200
invalid = []
for f in feats:
    g = shape(f["geometry"])
    if not g.is_valid:
        invalid.append(f["properties"]["state"])
    b = g.bounds
    lat_max = max(lat_max, b[3])
    lon_min = min(lon_min, b[0])
    lon_max = max(lon_max, b[2])
print(f"  northern extent    : {lat_max:.3f} N   "
      f"({'reaches claimed frontier' if lat_max >= 36.5 else 'TRUNCATED - REJECT'})")
print(f"  longitude range    : {lon_min:.2f} .. {lon_max:.2f}")
print(f"  invalid geometries : {len(invalid)} {invalid if invalid else ''}")

ok = (len(feats) == 36 and not missing and not extra
      and lat_max >= 36.5 and not invalid)
print(f"\n  VERDICT: {'PASS' if ok else 'FAIL'}")
if not ok:
    sys.exit("not written")

out = os.path.join(HERE, "india_states.geojson")
json.dump({"type": "FeatureCollection", "features": feats},
          open(out, "w", encoding="utf-8"))
print(f"\nwrote {out}  ({os.path.getsize(out)/1048576:.1f} MB)")

# a simplified copy for the browser
simp = []
for f in feats:
    g = shape(f["geometry"]).simplify(0.01, preserve_topology=True)
    simp.append({"type": "Feature", "properties": f["properties"], "geometry": mapping(g)})
outs = os.path.join(HERE, "india_states.simplified.geojson")
json.dump({"type": "FeatureCollection", "features": simp},
          open(outs, "w", encoding="utf-8"))
sl_max = max(shape(f["geometry"]).bounds[3] for f in simp)
print(f"wrote {outs}  ({os.path.getsize(outs)/1048576:.2f} MB), "
      f"northern extent preserved: {sl_max:.3f} N")
