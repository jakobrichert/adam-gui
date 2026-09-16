"""Synthetic ADAM-like results from a small forward-in-time breeding simulation.

Demo mode runs this instead of the ADAM executable. The model is deliberately
small but genuine: diploid genomes with recombination, additive QTL, selection
on estimated breeding values, and exact pedigree coancestry. Charts and 3D
views therefore show a real selection response, drift and inbreeding rather
than random noise.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from adam_gui.models.enums import (
    OrganismType, PropagationMethod, SelectionStrategy, SelectionUnit,
)
from adam_gui.models.parameters import ChromosomeSpec, SimulationParameters, TraitSpec
from adam_gui.models.results import (
    GenerationSummary, GenotypeData, IndividualRecord, MarkerInfo, QTLInfo,
    SimulationResults,
)

MAX_POPULATION = 2000
MAX_CHROMOSOMES = 10
MAX_MARKERS_PER_CHROM = 60
MAX_QTL_PER_CHROM = 50
MAX_STORED_GENOTYPE_GENERATIONS = 15
BASE_POPULATION = 50
BASE_GENERATIONS = 6

# Accuracy of EBVs relative to phenotypic selection (sqrt(h2)), per strategy.
_ACCURACY_BONUS = {
    SelectionStrategy.PHENOTYPIC: 0.0,
    SelectionStrategy.BLUP: 0.15,
    SelectionStrategy.GBLUP: 0.25,
    SelectionStrategy.SSGBLUP: 0.28,
    SelectionStrategy.BAYESIAN: 0.27,
    SelectionStrategy.OCS: 0.20,
}
_MAX_ACCURACY = 0.95

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


class DemoCancelled(Exception):
    """Raised by ``DemoDataGenerator.generate`` when ``should_cancel`` returns True."""


@dataclass
class _Genome:
    """Static genome layout. Loci are sorted by position within each chromosome."""

    chrom: np.ndarray          # (L,) 0-based chromosome index
    pos_cm: np.ndarray         # (L,)
    pos_mb: np.ndarray         # (L,)
    is_qtl: np.ndarray         # (L,) bool
    slices: list[slice]        # locus range of each chromosome
    lengths_m: list[float]     # chromosome lengths in Morgans

    @property
    def n_loci(self) -> int:
        return len(self.chrom)

    @property
    def marker_idx(self) -> np.ndarray:
        return np.flatnonzero(~self.is_qtl)

    @property
    def qtl_idx(self) -> np.ndarray:
        return np.flatnonzero(self.is_qtl)


class DemoDataGenerator:
    """Generate realistic synthetic breeding simulation results."""

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------ API

    def generate(
        self,
        params: Optional[SimulationParameters] = None,
        progress: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
    ) -> SimulationResults:
        started = time.perf_counter()
        if params is None:
            params = SimulationParameters()

        seed = self._seed
        if seed is None:
            seed = params.random_seed
        if seed is None:
            seed = int(np.random.SeedSequence().entropy % (2**32))
        self.rng = np.random.default_rng(seed)
        rng = self.rng

        traits = list(params.traits) or [TraitSpec()]
        n_traits = len(traits)
        n_gens = max(1, params.breeding.n_cycles * params.breeding.generations_per_cycle)
        gens_per_cycle = max(1, params.breeding.generations_per_cycle)
        n_pop = int(min(MAX_POPULATION, max(2, params.founder.n_paternal + params.founder.n_maternal)))
        is_animal = params.organism_type == OrganismType.ANIMAL
        male_frac = params.founder.n_paternal / max(1, params.founder.n_paternal + params.founder.n_maternal)
        n_males = int(min(n_pop - 1, max(1, round(n_pop * male_frac))))
        method = params.propagation.method
        n_offspring = max(1, params.propagation.n_offspring_per_cross)

        genome = self._build_genome(params)
        self._genome = genome
        hap = self._base_population(genome, n_pop)
        qtl_idx = genome.qtl_idx
        marker_idx = genome.marker_idx

        # Trait architecture, scaled so generation-0 TBV variance matches the target.
        dos_q0 = hap[:, :, qtl_idx].sum(axis=1).astype(float)
        effects = np.empty((n_traits, len(qtl_idx)))
        for t, trait in enumerate(traits):
            raw = rng.gamma(1.0, 1.0, len(qtl_idx)) * rng.choice([-1.0, 1.0], len(qtl_idx))
            var = (dos_q0 @ raw).var()
            target = max(trait.genetic_variance, 1e-6)
            effects[t] = raw * math.sqrt(target / var) if var > 0 else raw
        base_mean = (dos_q0 @ effects.T).mean(axis=0)
        base_sd = np.sqrt([max(t.genetic_variance, 1e-6) for t in traits])
        h2 = np.array([min(1.0, max(0.01, t.heritability)) for t in traits])
        env_sd = np.sqrt(base_sd**2 * (1.0 - h2) / h2)
        accuracy = np.minimum(
            _MAX_ACCURACY,
            np.sqrt(h2) + _ACCURACY_BONUS.get(params.selection.strategy, 0.0),
        )
        weights = np.array([t.economic_value for t in traits], dtype=float)
        if not np.any(weights):
            weights[0] = 1.0

        p0 = hap.mean(axis=(0, 1))
        h_exp = float(np.mean(2 * p0 * (1 - p0))) or 1.0

        stored_gens = self._stored_generations(n_gens)

        # Per-generation state.
        sexes = self._assign_sexes(n_pop, n_males, is_animal, founders=True)
        families = np.arange(n_pop)
        coancestry = np.eye(n_pop, dtype=np.float32) * 0.5
        ped_f = np.zeros(n_pop)
        sire_ids = np.zeros(n_pop, dtype=np.int64)
        dam_ids = np.zeros(n_pop, dtype=np.int64)
        next_id = 1

        individuals: list[IndividualRecord] = []
        generations: list[GenerationSummary] = []
        genotype_data: dict[int, GenotypeData] = {}
        pedigree_edges: list[tuple[int, int]] = []
        qtl_freqs = np.empty((n_gens, len(qtl_idx)))
        prev_mean_tbv: Optional[list[float]] = None

        for g in range(n_gens):
            if should_cancel is not None and should_cancel():
                raise DemoCancelled()

            ids = np.arange(next_id, next_id + n_pop, dtype=np.int64)
            next_id += n_pop

            dos_q = hap[:, :, qtl_idx].sum(axis=1).astype(float)
            tbv = dos_q @ effects.T - base_mean
            pheno = tbv + rng.normal(0.0, 1.0, tbv.shape) * env_sd
            ebv = self._estimate(tbv, accuracy)
            index = (ebv / base_sd) @ weights

            selected = self._select(
                params, index, sexes, families, coancestry, is_animal, n_pop,
            )

            het = (hap[:, 0, :] != hap[:, 1, :]).mean(axis=1)
            gen_f = np.clip(1.0 - het / h_exp, 0.0, 1.0)

            cycle = g // gens_per_cycle
            tbv_l, ebv_l, pheno_l = tbv.tolist(), ebv.tolist(), pheno.tolist()
            for i in range(n_pop):
                individuals.append(IndividualRecord(
                    individual_id=int(ids[i]),
                    generation=g,
                    cycle=cycle,
                    sire_id=int(sire_ids[i]),
                    dam_id=int(dam_ids[i]),
                    sex=str(sexes[i]),
                    tbv=tbv_l[i],
                    ebv=ebv_l[i],
                    phenotype=pheno_l[i],
                    inbreeding_pedigree=float(ped_f[i]),
                    inbreeding_genomic=float(gen_f[i]),
                    selected=bool(selected[i]),
                ))
            if g > 0:
                for i in range(n_pop):
                    pedigree_edges.append((int(sire_ids[i]), int(ids[i])))
                    if dam_ids[i] != sire_ids[i]:
                        pedigree_edges.append((int(dam_ids[i]), int(ids[i])))

            mean_tbv = tbv.mean(axis=0).tolist()
            between, within = self._variance_components(tbv, families, first=(g == 0))
            generations.append(GenerationSummary(
                generation=g,
                cycle=cycle,
                n_individuals=n_pop,
                mean_tbv=mean_tbv,
                mean_ebv=ebv.mean(axis=0).tolist(),
                mean_phenotype=pheno.mean(axis=0).tolist(),
                genetic_variance=_clean(tbv.var(axis=0)),
                variance_between_family=between,
                variance_within_family=within,
                mean_inbreeding=float(ped_f.mean()),
                selection_accuracy=[_corr(tbv[:, t], ebv[:, t]) for t in range(n_traits)],
                genetic_gain=(
                    [0.0] * n_traits if prev_mean_tbv is None
                    else [m - p for m, p in zip(mean_tbv, prev_mean_tbv, strict=True)]
                ),
            ))
            prev_mean_tbv = mean_tbv

            qtl_freqs[g] = hap[:, :, qtl_idx].mean(axis=(0, 1))
            if g == 0:
                marker_freq0 = hap[:, :, marker_idx].mean(axis=(0, 1))
            if g in stored_gens:
                genotype_data[g] = GenotypeData(
                    individual_ids=ids.copy(),
                    genotype_matrix=hap[:, :, marker_idx].sum(axis=1).astype(np.int8),
                    chromosome_indices=genome.chrom[marker_idx].copy(),
                    marker_positions_cm=genome.pos_cm[marker_idx].copy(),
                    marker_positions_mb=genome.pos_mb[marker_idx].copy(),
                )

            if g < n_gens - 1:
                sires, dams = self._mating_plan(
                    params, np.flatnonzero(selected), sexes, is_animal, n_pop, n_offspring,
                )
                hap = self._reproduce(hap, sires, dams, method)
                coancestry, ped_f = _next_coancestry(coancestry, sires, dams, method)
                sire_ids, dam_ids = ids[sires], ids[dams]
                families = _family_ids(sires, dams)
                sexes = self._assign_sexes(n_pop, n_males, is_animal, founders=False)

            if progress is not None:
                progress(g + 1, n_gens)

        marker_freq_last = hap[:, :, marker_idx].mean(axis=(0, 1))

        qtl_info = [
            QTLInfo(
                chromosome=int(genome.chrom[loc]),
                position_cm=float(genome.pos_cm[loc]),
                position_mb=float(genome.pos_mb[loc]),
                n_alleles=2,
                allele_effects=[float(effects[0, q]), 0.0],
                allele_frequencies=[[float(f), float(1.0 - f)] for f in qtl_freqs[:, q]],
            )
            for q, loc in enumerate(qtl_idx)
        ]
        marker_info = [
            MarkerInfo(
                chromosome=int(genome.chrom[loc]),
                position_cm=float(genome.pos_cm[loc]),
                allele_frequencies=[[float(marker_freq0[m])], [float(marker_freq_last[m])]],
            )
            for m, loc in enumerate(marker_idx)
        ]

        elapsed = time.perf_counter() - started
        first, last = generations[0], generations[-1]
        log_output = "\n".join([
            "ADAM GUI demo simulation (not an ADAM run)",
            f"Seed: {seed}",
            f"Generations: {n_gens}, individuals per generation: {n_pop}",
            f"Genome: {len(genome.slices)} chromosomes, {len(marker_idx)} markers, {len(qtl_idx)} QTL",
            f"Mean TBV ({traits[0].name}): {first.mean_tbv[0]:.3f} -> {last.mean_tbv[0]:.3f}",
            f"Genetic variance: {first.genetic_variance[0]:.3f} -> {last.genetic_variance[0]:.3f}",
            f"Mean pedigree inbreeding: {first.mean_inbreeding:.4f} -> {last.mean_inbreeding:.4f}",
            f"Elapsed: {elapsed:.2f} s",
        ])

        return SimulationResults(
            run_id=str(uuid.uuid4()),
            parameters=params,
            replicate=1,
            individuals=individuals,
            generations=generations,
            genotype_data=genotype_data,
            qtl_info=qtl_info,
            marker_info=marker_info,
            pedigree_edges=pedigree_edges,
            output_directory="",
            elapsed_seconds=elapsed,
            adam_version="demo",
            log_output=log_output,
        )

    # --------------------------------------------------------------- genome

    def _build_genome(self, params: SimulationParameters) -> _Genome:
        rng = self.rng
        n_chrom = max(1, min(params.founder.n_chromosomes, MAX_CHROMOSOMES))
        specs = list(params.founder.chromosomes[:n_chrom])
        specs += [ChromosomeSpec() for _ in range(n_chrom - len(specs))]
        force_qtl = all(min(s.n_qtl, MAX_QTL_PER_CHROM) <= 0 for s in specs)

        chrom, pos_cm, pos_mb, is_qtl, slices, lengths = [], [], [], [], [], []
        start = 0
        for c, spec in enumerate(specs):
            length_cm = max(float(spec.length_cm), 1.0)
            mb_per_cm = (spec.length_mb / length_cm) if spec.length_mb > 0 else 1.0
            n_m = max(1, min(spec.n_markers, MAX_MARKERS_PER_CHROM))
            n_q = 1 if force_qtl else max(0, min(spec.n_qtl, MAX_QTL_PER_CHROM))
            pos = rng.uniform(0.0, length_cm, n_m + n_q)
            flags = np.r_[np.zeros(n_m, bool), np.ones(n_q, bool)]
            order = np.argsort(pos)
            pos, flags = pos[order], flags[order]
            chrom.append(np.full(len(pos), c))
            pos_cm.append(pos)
            pos_mb.append(pos * mb_per_cm)
            is_qtl.append(flags)
            slices.append(slice(start, start + len(pos)))
            lengths.append(length_cm / 100.0)
            start += len(pos)

        return _Genome(
            chrom=np.concatenate(chrom),
            pos_cm=np.concatenate(pos_cm),
            pos_mb=np.concatenate(pos_mb),
            is_qtl=np.concatenate(is_qtl),
            slices=slices,
            lengths_m=lengths,
        )

    def _base_population(self, genome: _Genome, n_pop: int) -> np.ndarray:
        """Founders with LD: a small base population expanded by random mating."""
        rng = self.rng
        freq = np.clip(rng.beta(0.4, 0.4, genome.n_loci), 0.05, 0.95)
        hap = (rng.random((BASE_POPULATION, 2, genome.n_loci)) < freq).astype(np.int8)
        sizes = np.geomspace(BASE_POPULATION, n_pop, BASE_GENERATIONS + 1)[1:].round().astype(int)
        sizes[-1] = n_pop
        for size in sizes:
            sires = rng.integers(0, hap.shape[0], size)
            dams = rng.integers(0, hap.shape[0], size)
            hap = np.stack([self._gametes(hap, sires), self._gametes(hap, dams)], axis=1)

        # Re-seed loci lost to drift so every QTL and marker segregates.
        p = hap.mean(axis=(0, 1))
        mono = np.flatnonzero((p == 0) | (p == 1))
        if len(mono):
            flip = rng.random((n_pop, 2, len(mono))) < 0.3
            hap[:, :, mono] = np.where(flip, 1 - hap[:, :, mono], hap[:, :, mono])
        return hap

    def _gametes(self, hap: np.ndarray, parents: np.ndarray) -> np.ndarray:
        """One recombinant gamete per entry of ``parents``; ``hap`` is (N, 2, L)."""
        rng = self.rng
        genome = self._genome
        m = len(parents)
        out = np.empty((m, hap.shape[2]), dtype=np.int8)
        for sl, length_m in zip(genome.slices, genome.lengths_m, strict=True):
            pos_m = genome.pos_cm[sl] / 100.0
            strand = rng.integers(0, 2, (m, 1))
            n_co = rng.poisson(length_m, m)
            k = int(n_co.max()) if m else 0
            if k:
                crossovers = rng.random((m, k)) * length_m
                crossovers[np.arange(k)[None, :] >= n_co[:, None]] = np.inf
                strand = (strand + (crossovers[:, :, None] < pos_m[None, None, :]).sum(axis=1)) % 2
            segment = hap[parents, :, sl]
            out[:, sl] = np.where(strand == 0, segment[:, 0, :], segment[:, 1, :])
        return out

    def _reproduce(self, hap, sires, dams, method) -> np.ndarray:
        if method == PropagationMethod.CLONING:
            return hap[sires].copy()
        if method == PropagationMethod.DOUBLED_HAPLOID:
            gamete = self._gametes(hap, sires)
            return np.stack([gamete, gamete], axis=1)
        return np.stack([self._gametes(hap, sires), self._gametes(hap, dams)], axis=1)

    # ------------------------------------------------------------ selection

    def _estimate(self, tbv: np.ndarray, accuracy: np.ndarray) -> np.ndarray:
        """EBVs with correlation ``accuracy`` to TBV, regressed into TBV units."""
        ebv = np.empty_like(tbv)
        for t in range(tbv.shape[1]):
            mu, va, r = tbv[:, t].mean(), tbv[:, t].var(), accuracy[t]
            if va <= 0 or r >= 1:
                ebv[:, t] = tbv[:, t]
                continue
            noise_sd = math.sqrt(va * (1 - r * r)) / r
            raw = tbv[:, t] - mu + self.rng.normal(0.0, noise_sd, len(tbv))
            ebv[:, t] = mu + r * r * raw
        return ebv

    def _select(self, params, index, sexes, families, coancestry, is_animal, n_pop) -> np.ndarray:
        sel = params.selection
        selected = np.zeros(n_pop, dtype=bool)
        if is_animal:
            groups = [
                (np.flatnonzero(sexes == "M"), sel.truncation_proportion_male),
                (np.flatnonzero(sexes == "F"), sel.truncation_proportion_female),
            ]
        else:
            groups = [(np.arange(n_pop), sel.truncation_proportion_male)]

        use_ocs = sel.strategy == SelectionStrategy.OCS and sel.ocs_penalty_weight > 0
        chosen_so_far: list[int] = []
        for candidates, proportion in groups:
            if len(candidates) == 0:
                continue
            minimum = 1 if is_animal else 2
            n_sel = int(min(len(candidates), max(minimum, round(proportion * len(candidates)))))
            if use_ocs:
                picked = self._select_ocs(
                    candidates, n_sel, index, coancestry, sel.ocs_penalty_weight, chosen_so_far,
                )
            elif sel.unit == SelectionUnit.WITHIN_FAMILY:
                picked = _select_within_family(candidates, n_sel, index, families)
            elif sel.unit == SelectionUnit.FAMILY:
                picked = _select_families(candidates, n_sel, index, families)
            else:
                picked = candidates[np.argsort(-index[candidates], kind="stable")[:n_sel]]
            selected[picked] = True
            chosen_so_far.extend(int(i) for i in picked)
        return selected

    def _select_ocs(self, candidates, n_sel, index, coancestry, weight, already) -> np.ndarray:
        """Greedy optimum-contribution style selection penalising mean coancestry."""
        sd = index.std() or 1.0
        z = (index[candidates] - index.mean()) / sd
        chosen = list(already)
        sum_k = coancestry[chosen].sum(axis=0).astype(float) if chosen else np.zeros(len(index))
        available = np.ones(len(candidates), dtype=bool)
        picked = []
        for _ in range(n_sel):
            penalty = sum_k[candidates] / len(chosen) if chosen else 0.0
            score = np.where(available, z - weight * penalty, -np.inf)
            j = int(np.argmax(score))
            available[j] = False
            idx = int(candidates[j])
            picked.append(idx)
            chosen.append(idx)
            sum_k += coancestry[idx]
        return np.array(picked, dtype=int)

    # --------------------------------------------------------------- mating

    def _mating_plan(self, params, selected, sexes, is_animal, n_pop, n_offspring):
        """Return (sire, dam) index arrays for the next generation, one per offspring."""
        rng = self.rng
        method = params.propagation.method
        n_crosses = math.ceil(n_pop / n_offspring)

        if method != PropagationMethod.CROSSING:
            parents = self._balanced(selected, n_crosses)
            sires = dams = parents
        elif is_animal:
            males = selected[sexes[selected] == "M"]
            females = selected[sexes[selected] == "F"]
            if len(males) == 0 or len(females) == 0:
                males = females = selected
            sires = self._balanced(males, n_crosses)
            dams = self._balanced(females, n_crosses)
        else:
            sires = self._balanced(selected, n_crosses)
            dams = self._balanced(selected, n_crosses)
            if len(selected) > 1:
                for j in np.flatnonzero(sires == dams):
                    others = selected[selected != sires[j]]
                    dams[j] = rng.choice(others)

        sires = np.repeat(sires, n_offspring)[:n_pop]
        dams = np.repeat(dams, n_offspring)[:n_pop]
        return sires, dams

    def _balanced(self, pool: np.ndarray, n: int) -> np.ndarray:
        """Use every parent in ``pool`` as evenly as possible, in random order."""
        reps = np.resize(self.rng.permutation(pool), n)
        self.rng.shuffle(reps)
        return reps

    def _assign_sexes(self, n_pop, n_males, is_animal, founders: bool) -> np.ndarray:
        if not is_animal:
            return np.full(n_pop, "H")
        sexes = np.full(n_pop, "F")
        if founders:
            sexes[:n_males] = "M"
        else:
            sexes[self.rng.permutation(n_pop)[:n_males]] = "M"
        return sexes

    # ------------------------------------------------------------- summaries

    @staticmethod
    def _variance_components(tbv, families, first: bool) -> tuple[list[float], list[float]]:
        total = tbv.var(axis=0)
        if first:
            return _clean(total), [0.0] * tbv.shape[1]
        fam_ids, inverse, counts = np.unique(families, return_inverse=True, return_counts=True)
        sums = np.zeros((len(fam_ids), tbv.shape[1]))
        np.add.at(sums, inverse, tbv)
        means = sums / counts[:, None]
        between = means.var(axis=0)
        sq = np.zeros_like(sums)
        np.add.at(sq, inverse, (tbv - means[inverse]) ** 2)
        multi = counts > 1
        if multi.any():
            within = (sq[multi] / counts[multi, None]).mean(axis=0)
        else:
            within = np.zeros(tbv.shape[1])
        return _clean(between), _clean(within)

    @staticmethod
    def _stored_generations(n_gens: int) -> set[int]:
        if n_gens <= 20:
            return set(range(n_gens))
        points = np.linspace(0, n_gens - 1, MAX_STORED_GENOTYPE_GENERATIONS)
        return set(np.unique(points.round().astype(int)).tolist())


def _clean(values: np.ndarray) -> list[float]:
    """Variances as floats, with round-off noise after fixation shown as 0."""
    return np.where(np.abs(values) < 1e-12, 0.0, values).tolist()


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.clip(np.corrcoef(a, b)[0, 1], 0.0, 1.0))


def _family_ids(sires: np.ndarray, dams: np.ndarray) -> np.ndarray:
    """Full-sib family id per offspring (unordered parent pair)."""
    pairs = np.stack([np.minimum(sires, dams), np.maximum(sires, dams)], axis=1)
    _, inverse = np.unique(pairs, axis=0, return_inverse=True)
    return inverse.ravel()


def _next_coancestry(coancestry, sires, dams, method):
    """Coancestry matrix and pedigree F of the offspring generation."""
    k_s = coancestry[sires]
    if method == PropagationMethod.CLONING:
        k_next = k_s[:, sires]
        f = 2.0 * coancestry[sires, sires] - 1.0
        return k_next, f.astype(float)

    if method in (PropagationMethod.SELFING, PropagationMethod.DOUBLED_HAPLOID) or np.array_equal(sires, dams):
        k_next = k_s[:, sires]
    else:
        k_d = coancestry[dams]
        k_next = k_s[:, sires] + k_s[:, dams] + k_d[:, sires] + k_d[:, dams]
        k_next *= 0.25

    if method == PropagationMethod.DOUBLED_HAPLOID:
        f = np.ones(len(sires))
        np.fill_diagonal(k_next, 1.0)
    else:
        f = coancestry[sires, dams].astype(float)
        np.fill_diagonal(k_next, (1.0 + f) / 2.0)
    return k_next, f


def _select_within_family(candidates, n_sel, index, families) -> np.ndarray:
    """Best of each full-sib family first, then second-best, and so on."""
    ordered = candidates[np.argsort(-index[candidates], kind="stable")]
    seen: dict[int, int] = {}
    ranks = np.empty(len(ordered), dtype=int)
    for pos, idx in enumerate(ordered):
        fam = int(families[idx])
        ranks[pos] = seen.get(fam, 0)
        seen[fam] = ranks[pos] + 1
    order = np.lexsort((-index[ordered], ranks))
    return ordered[order[:n_sel]]


def _select_families(candidates, n_sel, index, families) -> np.ndarray:
    """Whole families ranked by mean index; the last family is trimmed to fit."""
    fams = families[candidates]
    fam_ids, inverse = np.unique(fams, return_inverse=True)
    means = np.bincount(inverse, weights=index[candidates]) / np.bincount(inverse)
    fam_rank = np.empty(len(fam_ids), dtype=int)
    fam_rank[np.argsort(-means, kind="stable")] = np.arange(len(fam_ids))
    order = np.lexsort((-index[candidates], fam_rank[inverse]))
    return candidates[order[:n_sel]]
