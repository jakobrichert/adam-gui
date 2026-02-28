"""Multi-run comparison and alignment logic."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from adam_gui.models.results import SimulationResults


@dataclass
class ComparisonMetric:
    """A single metric compared across runs."""
    name: str
    label: str
    generations: list[int]
    values_by_run: dict[str, list[float]]  # run_id -> values per generation


@dataclass
class ComparisonResult:
    """Full comparison of multiple simulation runs."""
    run_ids: list[str]
    run_labels: list[str]
    metrics: list[ComparisonMetric] = field(default_factory=list)
    summary: dict[str, dict[str, float]] = field(default_factory=dict)


class ComparisonService:
    """Compare multiple simulation runs side-by-side."""

    AVAILABLE_METRICS = [
        ("mean_tbv", "Mean TBV"),
        ("genetic_variance", "Genetic Variance"),
        ("mean_inbreeding", "Mean Inbreeding"),
        ("selection_accuracy", "Selection Accuracy"),
        ("genetic_gain", "Genetic Gain"),
    ]

    def compare(
        self,
        runs: list[SimulationResults],
        metrics: list[str] | None = None,
        trait_index: int = 0,
    ) -> ComparisonResult:
        """Compare multiple runs across specified metrics."""
        if not runs:
            return ComparisonResult(run_ids=[], run_labels=[])

        if metrics is None:
            metrics = [m[0] for m in self.AVAILABLE_METRICS]

        run_ids = [r.run_id for r in runs]
        run_labels = [
            r.parameters.name if r.parameters else f"Run {r.run_id[:8]}"
            for r in runs
        ]

        # Find common generation range
        all_gens = set()
        for r in runs:
            all_gens.update(r.generation_numbers)
        generations = sorted(all_gens)

        result = ComparisonResult(
            run_ids=run_ids,
            run_labels=run_labels,
        )

        for metric_name in metrics:
            label = dict(self.AVAILABLE_METRICS).get(metric_name, metric_name)
            values_by_run = {}

            for r in runs:
                series = r.get_metric_series(metric_name, trait_index)
                run_gens = r.generation_numbers
                # Align to common generation list
                gen_to_val = dict(zip(run_gens, series))
                aligned = [gen_to_val.get(g, float("nan")) for g in generations]
                values_by_run[r.run_id] = aligned

            result.metrics.append(ComparisonMetric(
                name=metric_name,
                label=label,
                generations=generations,
                values_by_run=values_by_run,
            ))

        # Summary statistics per run
        for r in runs:
            summary = {}
            gens = r.generations
            if gens:
                last = gens[-1]
                first = gens[0]
                summary["final_tbv"] = last.mean_tbv[trait_index] if last.mean_tbv else 0.0
                summary["total_gain"] = (
                    (last.mean_tbv[trait_index] if last.mean_tbv else 0.0) -
                    (first.mean_tbv[trait_index] if first.mean_tbv else 0.0)
                )
                summary["final_inbreeding"] = last.mean_inbreeding
                summary["final_variance"] = last.genetic_variance[trait_index] if last.genetic_variance else 0.0
                summary["n_generations"] = len(gens)
                summary["n_individuals"] = sum(g.n_individuals for g in gens)
                # Gain per unit inbreeding (efficiency)
                delta_f = last.mean_inbreeding - first.mean_inbreeding
                if abs(delta_f) > 1e-6:
                    summary["gain_per_inbreeding"] = summary["total_gain"] / delta_f
                else:
                    summary["gain_per_inbreeding"] = float("inf")
            result.summary[r.run_id] = summary

        return result

    def rank_runs(
        self,
        comparison: ComparisonResult,
        criterion: str = "total_gain",
        ascending: bool = False,
    ) -> list[str]:
        """Rank run IDs by a summary criterion."""
        items = []
        for run_id in comparison.run_ids:
            val = comparison.summary.get(run_id, {}).get(criterion, 0.0)
            items.append((run_id, val))
        items.sort(key=lambda x: x[1], reverse=not ascending)
        return [x[0] for x in items]
