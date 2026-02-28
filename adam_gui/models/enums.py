"""Enumerations for ADAM simulation configuration."""

from enum import Enum, auto


class GeneticModel(Enum):
    INFINITESIMAL = auto()
    GENOMIC = auto()


class SelectionStrategy(Enum):
    PHENOTYPIC = auto()
    BLUP = auto()
    GBLUP = auto()
    SSGBLUP = auto()
    BAYESIAN = auto()
    OCS = auto()


class SelectionUnit(Enum):
    INDIVIDUAL = auto()
    WITHIN_FAMILY = auto()
    FAMILY = auto()


class PropagationMethod(Enum):
    CLONING = auto()
    CROSSING = auto()
    SELFING = auto()
    DOUBLED_HAPLOID = auto()


class CrossingScheme(Enum):
    WITHIN_FAMILY = auto()
    ACROSS_FAMILY = auto()
    POPULATION_WIDE = auto()
    BACKCROSS = auto()
    THREE_WAY = auto()
    DOUBLE_CROSS = auto()


class PloidyLevel(Enum):
    DIPLOID = 2
    TETRAPLOID = 4
    HEXAPLOID = 6
    OCTAPLOID = 8


class OrganismType(Enum):
    ANIMAL = auto()
    PLANT_SELF_POLLINATED = auto()
    PLANT_CROSS_POLLINATED = auto()


class RunStatus(Enum):
    QUEUED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
