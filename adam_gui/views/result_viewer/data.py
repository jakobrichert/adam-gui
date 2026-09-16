"""Column-oriented, cached view of a SimulationResults for the result tabs."""

from __future__ import annotations

import math
from collections import OrderedDict

import numpy as np

from adam_gui.models.enums import OrganismType
from adam_gui.models.results import SimulationResults


def pretty_enum(value) -> str:
    if value is None:
        return "—"
    name = value.name if hasattr(value, "name") else str(value)
    special = {"BLUP": "BLUP", "GBLUP": "GBLUP", "SSGBLUP": "ssGBLUP", "OCS": "OCS"}
    if name in special:
        return special[name]
    return name.replace("_", " ").capitalize()


def fmt_num(v: float, digits: int = 3) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    if abs(v) < 1e-9:
        v = 0.0
    if v != 0 and abs(v) < 10 ** -(digits - 1):
        return f"{v:.2g}" if abs(v) >= 1e-4 else f"{v:.1e}"
    return f"{v:,.{digits}f}"


class RunData:
    """Numpy arrays of all individuals plus per-generation helpers."""

    def __init__(self, run: SimulationResults):
        self.run = run
        inds = run.individuals
        n = len(inds)
        self.n = n
        params = run.parameters
        self.n_traits = max(
            [len(i.tbv) for i in inds[:1]] + [len(g.mean_tbv) for g in run.generations[:1]] + [1]
        )
        names = [t.name for t in params.traits] if params else []
        while len(names) < self.n_traits:
            names.append(f"Trait {len(names) + 1}")
        self.trait_names = names[: self.n_traits]

        self.ids = np.fromiter((i.individual_id for i in inds), dtype=np.int64, count=n)
        self.gen = np.fromiter((i.generation for i in inds), dtype=np.int32, count=n)
        self.cycle = np.fromiter((i.cycle for i in inds), dtype=np.int32, count=n)
        self.sire = np.fromiter((i.sire_id or 0 for i in inds), dtype=np.int64, count=n)
        self.dam = np.fromiter((i.dam_id or 0 for i in inds), dtype=np.int64, count=n)
        self.sex = np.array([i.sex for i in inds], dtype="<U1") if n else np.array([], dtype="<U1")
        self.f_ped = np.fromiter((i.inbreeding_pedigree for i in inds), dtype=float, count=n)
        self.f_gen = np.fromiter((i.inbreeding_genomic for i in inds), dtype=float, count=n)
        self.selected = np.fromiter((bool(i.selected) for i in inds), dtype=bool, count=n)

        T = self.n_traits
        self.tbv = self._trait_matrix([i.tbv for i in inds], T)
        self.ebv = self._trait_matrix([i.ebv for i in inds], T)
        self.pheno = self._trait_matrix([i.phenotype for i in inds], T)
        self.row_of = {int(v): k for k, v in enumerate(self.ids)}

        self.generations = sorted(run.generations, key=lambda g: g.generation)
        self.gen_numbers = np.array([g.generation for g in self.generations], dtype=float)
        self.individual_generations = sorted(set(self.gen.tolist()))

        is_animal = params is not None and params.organism_type == OrganismType.ANIMAL
        self.has_sexes = bool(n) and (is_animal or bool(np.isin(self.sex, ["M", "F"]).any())) \
            and not bool((self.sex == "H").all())

    @staticmethod
    def _trait_matrix(rows: list[list[float]], T: int) -> np.ndarray:
        out = np.full((len(rows), T), np.nan)
        for k, r in enumerate(rows):
            if r:
                m = min(len(r), T)
                out[k, :m] = r[:m]
        return out

    # ------------------------------------------------------------ series
    def series(self, attr: str, trait: int = 0) -> np.ndarray:
        vals = []
        for g in self.generations:
            v = getattr(g, attr, None)
            if isinstance(v, list):
                vals.append(v[trait] if trait < len(v) else np.nan)
            elif v is None:
                vals.append(np.nan)
            else:
                vals.append(float(v))
        return np.asarray(vals, dtype=float)

    def has_series(self, attr: str) -> bool:
        s = self.series(attr)
        return bool(len(s)) and bool(np.isfinite(s).any())

    def per_generation_mean(self, values: np.ndarray) -> np.ndarray:
        """Mean of an individual-level array per summary generation."""
        out = np.full(len(self.generations), np.nan)
        if not self.n:
            return out
        for k, g in enumerate(self.generations):
            m = self.gen == g.generation
            if m.any():
                col = values[m]
                col = col[np.isfinite(col)]
                if col.size:
                    out[k] = col.mean()
        return out

    # ------------------------------------------------------------ metrics
    def delta_f(self) -> float:
        """Rate of inbreeding per generation from the pedigree F trajectory."""
        f = self.series("mean_inbreeding")
        f = f[np.isfinite(f)]
        if len(f) < 2:
            return float("nan")
        t = len(f) - 1
        f0, ft = min(f[0], 0.999), min(f[-1], 0.999)
        ratio = (1 - ft) / (1 - f0)
        if ratio <= 0:
            return float("nan")
        return 1 - ratio ** (1 / t)

    def effective_size(self) -> float:
        df = self.delta_f()
        if not np.isfinite(df) or df <= 1e-9:
            return float("nan")
        return 1.0 / (2.0 * df)

    def family_stats(self) -> dict:
        has_parents = (self.sire > 0) | (self.dam > 0)
        founders = int((~has_parents).sum())
        if has_parents.any():
            keys = self.sire[has_parents] * 10_000_003 + self.dam[has_parents]
            _, counts = np.unique(keys, return_counts=True)
            mean_family = float(counts.mean())
            n_families = int(len(counts))
        else:
            mean_family, n_families = float("nan"), 0
        sires, dams = [], []
        for g in self.individual_generations:
            m = (self.gen == g) & has_parents
            if m.any():
                sires.append(len(np.unique(self.sire[m])))
                dams.append(len(np.unique(self.dam[m])))
        return {
            "founders": founders,
            "families": n_families,
            "mean_family": mean_family,
            "sires_per_gen": float(np.mean(sires)) if sires else float("nan"),
            "dams_per_gen": float(np.mean(dams)) if dams else float("nan"),
            "single_parent": bool(has_parents.any() and np.all(self.sire[has_parents] == self.dam[has_parents])),
        }

    # ------------------------------------------------------------ pedigree
    def children_index(self) -> dict[int, list[int]]:
        if not hasattr(self, "_children"):
            children: dict[int, list[int]] = {}
            for k in range(self.n):
                cid = int(self.ids[k])
                s, d = int(self.sire[k]), int(self.dam[k])
                if s:
                    children.setdefault(s, []).append(cid)
                if d and d != s:
                    children.setdefault(d, []).append(cid)
            self._children = children
        return self._children

    def descendants_by_generation(self, ind_id: int, max_depth: int = 50) -> dict[int, int]:
        children = self.children_index()
        seen: set[int] = set()
        frontier = [ind_id]
        depth = 0
        while frontier and depth < max_depth:
            nxt = []
            for pid in frontier:
                for c in children.get(pid, ()):
                    if c not in seen:
                        seen.add(c)
                        nxt.append(c)
            frontier = nxt
            depth += 1
        counts: dict[int, int] = {}
        for c in seen:
            row = self.row_of.get(c)
            if row is not None:
                g = int(self.gen[row])
                counts[g] = counts.get(g, 0) + 1
        return dict(sorted(counts.items()))


_CACHE: "OrderedDict[str, RunData]" = OrderedDict()


def run_data(run: SimulationResults) -> RunData:
    key = f"{run.run_id}:{id(run)}"
    data = _CACHE.get(key)
    if data is None or data.run is not run:
        data = RunData(run)
        _CACHE[key] = data
        while len(_CACHE) > 6:
            _CACHE.popitem(last=False)
    else:
        _CACHE.move_to_end(key)
    return data


def safe_pct(new: float, old: float) -> float:
    if old is None or not np.isfinite(old) or abs(old) < 1e-12:
        return float("nan")
    return (new - old) / abs(old) * 100.0


def isfinite(v) -> bool:
    try:
        return v is not None and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def fit_empty_state(empty, width: int = 440) -> None:
    """Size an EmptyState's wrapped message so it is never clipped."""
    msg = empty.message
    msg.ensurePolished()
    msg.setFixedWidth(width)
    msg.setMinimumHeight(msg.heightForWidth(width) + 4)
