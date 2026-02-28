"""Tests for pedigree tree model."""

import pytest

from adam_gui.models.pedigree import PedigreeTree, PedigreeNode


class TestPedigreeTree:
    def test_construction(self, sample_individuals):
        tree = PedigreeTree(sample_individuals)
        assert tree.n_nodes == 30  # 3 generations * 10

    def test_by_generation(self, pedigree_tree):
        gens = pedigree_tree.by_generation()
        assert len(gens) == 3
        assert len(gens[0]) == 10
        assert len(gens[1]) == 10
        assert len(gens[2]) == 10

    def test_ancestors(self, pedigree_tree):
        # Individual 11 (gen 1) should have ancestors in gen 0
        ancestors = pedigree_tree.ancestors(11, max_depth=1)
        assert len(ancestors) > 0
        # All ancestors should be gen 0
        for anc in ancestors:
            assert anc.generation == 0

    def test_ancestors_depth_limit(self, pedigree_tree):
        # With depth 0, no ancestors
        ancestors = pedigree_tree.ancestors(21, max_depth=0)
        assert len(ancestors) == 0

    def test_descendants(self, pedigree_tree):
        # Individual 1 (gen 0) should have descendants in gen 1
        descendants = pedigree_tree.descendants(1, max_depth=1)
        assert len(descendants) > 0

    def test_get_edges(self, pedigree_tree):
        edges = pedigree_tree.get_edges()
        assert len(edges) > 0
        # Edges should be parent->child tuples
        for parent_id, child_id in edges:
            parent = pedigree_tree.nodes[parent_id]
            child = pedigree_tree.nodes[child_id]
            assert parent.generation < child.generation

    def test_subpedigree(self, pedigree_tree):
        ids = [1, 2, 11, 12]
        sub = pedigree_tree.subpedigree(ids)
        assert sub.n_nodes == 4
        # Edges outside subset should be removed
        for node in sub.nodes.values():
            if node.sire_id:
                assert node.sire_id in ids
            if node.dam_id:
                assert node.dam_id in ids

    def test_n_generations(self, pedigree_tree):
        assert pedigree_tree.n_generations == 3

    def test_empty_tree(self):
        tree = PedigreeTree()
        assert tree.n_nodes == 0
        assert tree.n_generations == 0
        assert tree.get_edges() == []
