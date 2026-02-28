"""Generate synthetic simulation results for demo mode."""

from __future__ import annotations

import uuid
from typing import Optional

import numpy as np

from adam_gui.models.parameters import SimulationParameters
from adam_gui.models.results import (
    SimulationResults, IndividualRecord, GenerationSummary,
    GenotypeData, QTLInfo, MarkerInfo,
)


class DemoDataGenerator:
    """Generate realistic synthetic breeding simulation results."""

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def generate(self, params: Optional[SimulationParameters] = None) -> SimulationResults:
        if params is None:
            params = SimulationParameters()

        n_gens = params.breeding.n_cycles * params.breeding.generations_per_cycle
        n_traits = len(params.traits)
        n_per_gen = params.founder.n_paternal + params.founder.n_maternal
        n_markers = min(200, sum(c.n_markers for c in params.founder.chromosomes[:3]))
        n_qtl = min(30, sum(c.n_qtl for c in params.founder.chromosomes[:3]))

        individuals = []
        generations = []
        pedigree_edges = []
        genotype_data = {}
        qtl_info = []
        marker_info = []

        id_counter = 1
        prev_gen_ids = []

        # Genetic gain trajectory
        gain_per_gen = 0.15 + self.rng.uniform(0, 0.1)
        variance_decay = 0.98

        current_variance = [t.genetic_variance for t in params.traits]
        current_mean_tbv = [0.0] * n_traits

        for gen in range(n_gens):
            gen_ids = []
            gen_tbvs = []
            gen_ebvs = []
            gen_phenotypes = []
            gen_inbreeding = []

            # Selection pressure increases inbreeding slowly
            mean_f = min(0.5, 0.001 * gen ** 1.3)

            for i in range(n_per_gen):
                ind_id = id_counter
                id_counter += 1
                gen_ids.append(ind_id)

                sex = "M" if i < n_per_gen // 2 else "F"

                # Assign parents from previous generation
                sire_id = 0
                dam_id = 0
                if prev_gen_ids and len(prev_gen_ids) >= 2:
                    sire_id = int(self.rng.choice(prev_gen_ids[:len(prev_gen_ids) // 2]))
                    dam_id = int(self.rng.choice(prev_gen_ids[len(prev_gen_ids) // 2:]))
                    pedigree_edges.append((sire_id, ind_id))
                    pedigree_edges.append((dam_id, ind_id))

                # Generate breeding values with genetic gain trend
                tbv = []
                ebv = []
                pheno = []
                for t_idx in range(n_traits):
                    true_bv = current_mean_tbv[t_idx] + self.rng.normal(0, np.sqrt(current_variance[t_idx]))
                    est_bv = true_bv + self.rng.normal(0, np.sqrt(current_variance[t_idx]) * 0.5)
                    h2 = params.traits[t_idx].heritability
                    env_var = current_variance[t_idx] * (1 - h2) / h2 if h2 > 0 else 1.0
                    phenotype = true_bv + self.rng.normal(0, np.sqrt(env_var))
                    tbv.append(float(true_bv))
                    ebv.append(float(est_bv))
                    pheno.append(float(phenotype))

                gen_tbvs.append(tbv)
                gen_ebvs.append(ebv)
                gen_phenotypes.append(pheno)

                f_ped = float(max(0, mean_f + self.rng.normal(0, 0.01)))
                gen_inbreeding.append(f_ped)

                # Top fraction selected
                selected = i < int(n_per_gen * params.selection.truncation_proportion_male) if sex == "M" \
                    else i - n_per_gen // 2 < int(n_per_gen // 2 * params.selection.truncation_proportion_female)

                individuals.append(IndividualRecord(
                    individual_id=ind_id,
                    generation=gen,
                    cycle=gen // max(1, params.breeding.generations_per_cycle),
                    sire_id=sire_id,
                    dam_id=dam_id,
                    sex=sex,
                    tbv=tbv,
                    ebv=ebv,
                    phenotype=pheno,
                    inbreeding_pedigree=f_ped,
                    inbreeding_genomic=float(f_ped * 0.9),
                    selected=selected,
                ))

            # Generation summary
            gen_tbvs_arr = np.array(gen_tbvs)
            gen_ebvs_arr = np.array(gen_ebvs)
            gen_pheno_arr = np.array(gen_phenotypes)

            mean_tbv = gen_tbvs_arr.mean(axis=0).tolist()
            mean_ebv = gen_ebvs_arr.mean(axis=0).tolist()
            mean_pheno = gen_pheno_arr.mean(axis=0).tolist()
            gen_var = gen_tbvs_arr.var(axis=0).tolist()

            # Selection accuracy
            acc = []
            for t_idx in range(n_traits):
                corr = np.corrcoef(gen_tbvs_arr[:, t_idx], gen_ebvs_arr[:, t_idx])[0, 1]
                acc.append(float(max(0, min(1, corr))))

            genetic_gain = [mean_tbv[t] - current_mean_tbv[t] for t in range(n_traits)]

            generations.append(GenerationSummary(
                generation=gen,
                cycle=gen // max(1, params.breeding.generations_per_cycle),
                n_individuals=n_per_gen,
                mean_tbv=mean_tbv,
                mean_ebv=mean_ebv,
                mean_phenotype=mean_pheno,
                genetic_variance=gen_var,
                variance_between_family=[v * 0.6 for v in gen_var],
                variance_within_family=[v * 0.4 for v in gen_var],
                mean_inbreeding=float(np.mean(gen_inbreeding)),
                selection_accuracy=acc,
                genetic_gain=genetic_gain,
            ))

            # Update for next generation
            for t_idx in range(n_traits):
                current_mean_tbv[t_idx] += gain_per_gen * np.sqrt(current_variance[t_idx])
                current_variance[t_idx] *= variance_decay

            # Genotype data (subsample for memory)
            if gen % max(1, n_gens // 10) == 0 or gen == n_gens - 1:
                n_chrom = min(3, params.founder.n_chromosomes)
                markers_per_chrom = n_markers // n_chrom
                chrom_indices = np.repeat(np.arange(n_chrom), markers_per_chrom)
                positions = np.tile(np.linspace(0, 100, markers_per_chrom), n_chrom)
                total_markers = len(chrom_indices)

                # Generate genotypes with LD structure
                geno = np.zeros((n_per_gen, total_markers), dtype=np.int8)
                for c in range(n_chrom):
                    mask = chrom_indices == c
                    n_m = mask.sum()
                    # Correlated genotypes within chromosome
                    base_freq = self.rng.uniform(0.1, 0.9, n_m)
                    for ind in range(n_per_gen):
                        alleles = (self.rng.random(n_m) < base_freq).astype(np.int8)
                        alleles += (self.rng.random(n_m) < base_freq).astype(np.int8)
                        geno[ind, mask] = alleles

                genotype_data[gen] = GenotypeData(
                    individual_ids=np.array(gen_ids),
                    genotype_matrix=geno,
                    chromosome_indices=chrom_indices,
                    marker_positions_cm=positions,
                    marker_positions_mb=positions * 1.5,
                )

            prev_gen_ids = gen_ids

        # QTL info
        for q in range(n_qtl):
            chrom = q % min(3, params.founder.n_chromosomes)
            pos = self.rng.uniform(0, 100)
            effect = float(self.rng.exponential(0.3) * self.rng.choice([-1, 1], p=[0.9, 0.1]))
            freqs = []
            f = self.rng.uniform(0.2, 0.8)
            for gen in range(n_gens):
                f = np.clip(f + self.rng.normal(0, 0.02), 0.01, 0.99)
                freqs.append([float(f), float(1 - f)])
            qtl_info.append(QTLInfo(
                chromosome=chrom,
                position_cm=float(pos),
                position_mb=float(pos * 1.5),
                n_alleles=2,
                allele_effects=[effect, 0.0],
                allele_frequencies=freqs,
            ))

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
            elapsed_seconds=0.0,
            adam_version="demo",
            log_output="Demo data generated successfully.",
        )
