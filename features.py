"""Point-in-time features. A feature CANNOT see the future — not by discipline, by construction.

Window holds only rows <= t. There is no accessor that returns a later row.
The @feature decorator's `reads` declaration is a SECOND layer, checked by
assert_no_leakage(), which catches declaration mistakes.
"""
import numpy as np, pandas as pd

REGISTRY = {}


def feature(reads):
    """reads: 't', 't-3..t', 't-inf..t'. Anything containing 't+' is rejected at lint time."""
    def deco(fn):
        REGISTRY[fn.__name__] = {"fn": fn, "reads": reads}
        return fn
    return deco


class LeakageError(AssertionError):
    pass


def assert_no_leakage(names=None):
    bad = [n for n, m in REGISTRY.items()
           if (names is None or n in names) and "t+" in m["reads"].replace(" ", "")]
    if bad:
        raise LeakageError(f"features read the future: {bad}")
    return True


class Window:
    """Rows for ONE project, truncated at t. Cannot expose the future."""
    __slots__ = ("_r", "_i", "t")

    def __init__(self, proj_rows, i):
        self._r = proj_rows            # dict of numpy arrays, sorted by t ascending
        self._i = i                    # index of the current month
        self.t = proj_rows["t"][i]

    def at(self, col):
        return self._r[col][self._i]

    def lag(self, col, k):
        j = self._i - k
        return self._r[col][j] if j >= 0 else np.nan

    def delta(self, col, k):
        a, b = self.at(col), self.lag(col, k)
        return np.nan if (pd.isna(a) or pd.isna(b)) else a - b

    def history(self, col):
        return self._r[col][: self._i + 1]        # inclusive of t, never beyond

    def nobs(self):
        return self._i


# ---------------------------------------------------------------- features
@feature(reads="t")
def original_cost(w): return w.at("original_cost")


@feature(reads="t")
def cost(w):
    rc, oc = w.at("revised_cost"), w.at("original_cost")
    return oc if pd.isna(rc) else rc


@feature(reads="t")
def expenditure(w): return w.at("expenditure")


@feature(reads="t")
def physical_progress(w): return w.at("physical_progress")


@feature(reads="t")
def fin_pct(w):
    c, e = cost(w), w.at("expenditure")
    return np.nan if (pd.isna(c) or pd.isna(e) or c == 0) else 100.0 * e / c


@feature(reads="t")
def gap(w):
    """physical progress minus financial progress: building fast vs paying fast"""
    p, f = w.at("physical_progress"), fin_pct(w)
    return np.nan if (pd.isna(p) or pd.isna(f)) else p - f


@feature(reads="t")
def mons_since_sanction(w):
    s = w.at("sanction_date")
    return np.nan if pd.isna(s) else (w.t - s).days / 30.44


@feature(reads="t")
def mons_to_due(w):
    """months until the CURRENT deadline. Strongest single feature (perm. importance 0.178)."""
    d = w.at("revised_date")
    if pd.isna(d):
        d = w.at("original_end_date")
    return np.nan if pd.isna(d) else (d - w.t).days / 30.44


@feature(reads="t")
def overdue(w):
    m = mons_to_due(w)
    return np.nan if pd.isna(m) else float(m < 0)


@feature(reads="t")
def cur_slip(w):
    """days already slipped. Known at t, so legitimate as a feature."""
    r, o = w.at("revised_date"), w.at("original_end_date")
    return np.nan if (pd.isna(r) or pd.isna(o)) else float((r - o).days)


@feature(reads="t-inf..t")
def prior_revs(w):
    """count of deadline changes strictly BEFORE t. AUC 0.623 on its own."""
    h = w.history("revised_ord")
    if len(h) < 2:
        return 0.0
    a, b = h[:-1], h[1:]
    ok = ~pd.isna(a) & ~pd.isna(b)          # same rule as _changed: both must exist
    return float(np.sum(ok & (a != b)))


@feature(reads="t-3..t")
def pp_delta_3m(w): return w.delta("physical_progress", 3)


@feature(reads="t-3..t")
def exp_delta_3m(w): return w.delta("expenditure", 3)


@feature(reads="t-inf..t")
def nobs(w):
    """months observed. REQUIRED: controls the onboarding ramp 791 -> 1987."""
    return float(w.nobs())


CORE = list(REGISTRY.keys())


# ---------------------------------------------------------------- build
def _prep(df):
    d = df.sort_values(["pid", "t"]).copy()
    d["revised_ord"] = d.revised_date.map(lambda x: np.nan if pd.isna(x) else x.toordinal())
    return d


def label_windows(df, horizon=3):
    """SEPARATE from features on purpose. Reads t+1..t+h. Never importable into a feature."""
    d = _prep(df)
    out = {}
    for pid, gr in d.groupby("pid", sort=False):
        ro = gr.revised_ord.to_numpy()
        rc = gr.revised_cost.to_numpy()
        months = gr.month.to_numpy()
        n = len(gr)
        for i in range(n):
            fut = range(i + 1, min(i + 1 + horizon, n))
            if not len(fut):
                out[(pid, months[i])] = (None, None)   # no future -> DROP, never 0
                continue
            sched = any(_changed(ro[j - 1], ro[j]) for j in fut)
            cost_ = any(_changed(rc[j - 1], rc[j]) for j in fut)
            out[(pid, months[i])] = (float(sched), float(cost_))
    return out


def _changed(a, b):
    """A deadline MOVED. Requires a deadline at both ends.

    NaN->value is a value APPEARING, which across this panel is migration backfill
    (1,851 events, clustered in 2025-07 / 2025-12 / 2026-03 onboarding waves), not a
    project slipping. Counting those inflates the base rate 0.263 -> 0.306 and costs
    ~7 AUC points of real signal. See 00_FINDINGS.md 3.5."""
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(a - b) > 1e-9


def build_matrix(df, names=None, horizon=3, require_label=True):
    """-> (X, meta), one row per (pid, month).

    require_label=True  (training): drop rows with no observable future. Never fill 0.
    require_label=False (scoring):  keep them; y_* is NaN for the latest month.
    """
    assert_no_leakage(names)
    names = names or CORE
    d = _prep(df)
    labels = label_windows(df, horizon)
    cols = ["t", "revised_cost", "original_cost", "expenditure", "physical_progress",
            "sanction_date", "original_end_date", "revised_date", "revised_ord"]
    X, meta = [], []
    for pid, gr in d.groupby("pid", sort=False):
        arr = {c: gr[c].to_numpy() for c in cols}
        months = gr.month.to_numpy()
        for i in range(len(gr)):
            y_s, y_c = labels[(pid, months[i])]
            if y_s is None:
                if require_label:
                    continue
                y_s = y_c = np.nan
            w = Window(arr, i)
            X.append([REGISTRY[n]["fn"](w) for n in names])
            meta.append((pid, months[i], gr.t.iloc[i], gr.name.iloc[i], gr.sector.iloc[i],
                         gr.ministry.iloc[i], gr.agency.iloc[i], gr.state.iloc[i], y_s, y_c))
    X = pd.DataFrame(X, columns=names)
    meta = pd.DataFrame(meta, columns=["pid", "month", "t", "name", "sector",
                                       "ministry", "agency", "state", "y_schedule", "y_cost"])
    return X, meta


def demo():
    assert assert_no_leakage()

    @feature(reads="t+1..t+3")
    def _cheater(w): return 1.0
    try:
        assert_no_leakage()
        raise SystemExit("LINTER FAILED TO CATCH THE FUTURE-READING FEATURE")
    except LeakageError:
        pass
    finally:
        REGISTRY.pop("_cheater")
    assert assert_no_leakage()
    print("features.py OK — linter catches t+k in both directions")


if __name__ == "__main__":
    demo()
