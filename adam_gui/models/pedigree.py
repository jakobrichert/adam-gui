"""Pedigree graph data structure with traversal methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from .results import IndividualRecord


@dataclass
class PedigreeNode:
    individual_id: int = 0
    generation: int = 0
    sex: str = "M"
    sire_id: int | None = None
    dam_id: int | None = None
    tbv: float = 0.0
    ebv: float = 0.0
    inbreeding: float = 0.0
    selected: bool = False
    children: list[int] = field(default_factory=list)


class PedigreeTree:
    """Efficient pedigree graph for traversal and visualization."""

    def __init__(self, individuals: list[IndividualRecord] | None = None):
        self.nodes: dict[int, PedigreeNode] = {}
        if individuals:
            self._build(individuals)

    def _build(self, individuals: list[IndividualRecord]) -> None:
        for ind in individuals:
            node = PedigreeNode(
                individual_id=ind.individual_id,
                generation=ind.generation,
                sex=ind.sex,
                sire_id=ind.sire_id if ind.sire_id else None,
                dam_id=ind.dam_id if ind.dam_id else None,
                tbv=ind.tbv[0] if ind.tbv else 0.0,
                ebv=ind.ebv[0] if ind.ebv else 0.0,
                inbreeding=ind.inbreeding_pedigree,
                selected=ind.selected,
            )
            self.nodes[ind.individual_id] = node

        # Build children links
        for node in self.nodes.values():
            if node.sire_id and node.sire_id in self.nodes:
                self.nodes[node.sire_id].children.append(node.individual_id)
            if node.dam_id and node.dam_id in self.nodes:
                self.nodes[node.dam_id].children.append(node.individual_id)

    def ancestors(self, id: int, max_depth: int = 100) -> list[PedigreeNode]:
        """Get all ancestors up to max_depth generations back."""
        result = []
        visited = set()
        stack = [(id, 0)]
        while stack:
            current_id, depth = stack.pop()
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            node = self.nodes.get(current_id)
            if node is None:
                continue
            if current_id != id:
                result.append(node)
            if node.sire_id and node.sire_id in self.nodes:
                stack.append((node.sire_id, depth + 1))
            if node.dam_id and node.dam_id in self.nodes:
                stack.append((node.dam_id, depth + 1))
        return result

    def descendants(self, id: int, max_depth: int = 100) -> list[PedigreeNode]:
        """Get all descendants up to max_depth generations forward."""
        result = []
        visited = set()
        stack = [(id, 0)]
        while stack:
            current_id, depth = stack.pop()
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            node = self.nodes.get(current_id)
            if node is None:
                continue
            if current_id != id:
                result.append(node)
            for child_id in node.children:
                stack.append((child_id, depth + 1))
        return result

    def by_generation(self) -> dict[int, list[PedigreeNode]]:
        """Group nodes by generation."""
        gens: dict[int, list[PedigreeNode]] = defaultdict(list)
        for node in self.nodes.values():
            gens[node.generation].append(node)
        return dict(gens)

    def subpedigree(self, ids: list[int]) -> PedigreeTree:
        """Extract a sub-pedigree containing only the specified individuals and their connections."""
        tree = PedigreeTree()
        id_set = set(ids)
        for id in ids:
            if id in self.nodes:
                tree.nodes[id] = PedigreeNode(
                    individual_id=self.nodes[id].individual_id,
                    generation=self.nodes[id].generation,
                    sex=self.nodes[id].sex,
                    sire_id=self.nodes[id].sire_id if self.nodes[id].sire_id in id_set else None,
                    dam_id=self.nodes[id].dam_id if self.nodes[id].dam_id in id_set else None,
                    tbv=self.nodes[id].tbv,
                    ebv=self.nodes[id].ebv,
                    inbreeding=self.nodes[id].inbreeding,
                    selected=self.nodes[id].selected,
                    children=[c for c in self.nodes[id].children if c in id_set],
                )
        return tree

    def get_edges(self) -> list[tuple[int, int]]:
        """Return all parent->child edges."""
        edges = []
        for node in self.nodes.values():
            if node.sire_id and node.sire_id in self.nodes:
                edges.append((node.sire_id, node.individual_id))
            if node.dam_id and node.dam_id in self.nodes:
                edges.append((node.dam_id, node.individual_id))
        return edges

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_generations(self) -> int:
        if not self.nodes:
            return 0
        gens = {n.generation for n in self.nodes.values()}
        return max(gens) - min(gens) + 1
