"""3D pedigree network visualization pipeline."""

import numpy as np

from vtkmodules.vtkCommonCore import vtkPoints, vtkFloatArray, vtkIdList
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkCellArray, vtkLine
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkFiltersCore import vtkGlyph3D, vtkTubeFilter
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.vtk_pipelines.common import make_diverging_lut, add_scalar_bar
from adam_gui.models.pedigree import PedigreeTree


class PedigreePipeline:
    """Build a 3D pedigree network from a PedigreeTree."""

    def build(self, renderer: vtkRenderer, pedigree: PedigreeTree, color_by: str = "tbv"):
        """Construct the full 3D pedigree visualization."""
        renderer.RemoveAllViewProps()

        if pedigree.n_nodes == 0:
            return

        gens = pedigree.by_generation()
        gen_keys = sorted(gens.keys())

        # Compute 3D positions: X=within-gen, Y=generation, Z=family grouping
        positions = {}
        node_data = {}

        for gen_idx, gen_num in enumerate(gen_keys):
            nodes = gens[gen_num]
            n = len(nodes)
            for i, node in enumerate(nodes):
                x = (i - n / 2) * 2.0
                y = gen_idx * 5.0
                # Z based on sire to create family clusters
                z = 0.0
                if node.sire_id and node.sire_id in positions:
                    z = positions[node.sire_id][2] + np.random.uniform(-0.5, 0.5)
                positions[node.individual_id] = (x, y, z)
                node_data[node.individual_id] = node

        # Build node points
        points = vtkPoints()
        scalars = vtkFloatArray()
        scalars.SetName(color_by.upper())
        sizes = vtkFloatArray()
        sizes.SetName("Size")

        id_to_vtk_idx = {}
        for nid, pos in positions.items():
            idx = points.InsertNextPoint(*pos)
            id_to_vtk_idx[nid] = idx
            node = node_data[nid]
            if color_by == "tbv":
                scalars.InsertNextValue(node.tbv)
            elif color_by == "inbreeding":
                scalars.InsertNextValue(node.inbreeding)
            else:
                scalars.InsertNextValue(node.generation)
            sizes.InsertNextValue(0.6 if node.selected else 0.3)

        # Node polydata
        node_pd = vtkPolyData()
        node_pd.SetPoints(points)
        node_pd.GetPointData().SetScalars(scalars)
        node_pd.GetPointData().AddArray(sizes)

        # Glyph nodes as spheres
        sphere = vtkSphereSource()
        sphere.SetRadius(1.0)
        sphere.SetPhiResolution(12)
        sphere.SetThetaResolution(12)

        # Use Size array as the active scalars for glyph scaling,
        # then switch back to color scalars for the mapper
        node_pd.GetPointData().SetActiveScalars("Size")

        glyph = vtkGlyph3D()
        glyph.SetInputData(node_pd)
        glyph.SetSourceConnection(sphere.GetOutputPort())
        glyph.SetScaleModeToScaleByScalar()
        glyph.SetScaleFactor(1.0)
        glyph.SetColorModeToColorByScalar()

        # Restore color scalars
        node_pd.GetPointData().SetActiveScalars(color_by.upper())

        # Color lookup table
        lut = make_diverging_lut()
        scalar_range = scalars.GetRange()
        lut.SetTableRange(scalar_range)

        node_mapper = vtkPolyDataMapper()
        node_mapper.SetInputConnection(glyph.GetOutputPort())
        node_mapper.SetLookupTable(lut)
        node_mapper.SetScalarRange(scalar_range)

        node_actor = vtkActor()
        node_actor.SetMapper(node_mapper)
        renderer.AddActor(node_actor)

        # Build edges
        edge_points = vtkPoints()
        edge_lines = vtkCellArray()

        edges = pedigree.get_edges()
        for parent_id, child_id in edges:
            if parent_id in positions and child_id in positions:
                p1 = edge_points.InsertNextPoint(*positions[parent_id])
                p2 = edge_points.InsertNextPoint(*positions[child_id])
                line = vtkLine()
                line.GetPointIds().SetId(0, p1)
                line.GetPointIds().SetId(1, p2)
                edge_lines.InsertNextCell(line)

        edge_pd = vtkPolyData()
        edge_pd.SetPoints(edge_points)
        edge_pd.SetLines(edge_lines)

        # Tube filter for edges
        tube = vtkTubeFilter()
        tube.SetInputData(edge_pd)
        tube.SetRadius(0.08)
        tube.SetNumberOfSides(6)

        edge_mapper = vtkPolyDataMapper()
        edge_mapper.SetInputConnection(tube.GetOutputPort())

        edge_actor = vtkActor()
        edge_actor.SetMapper(edge_mapper)
        edge_actor.GetProperty().SetColor(0.4, 0.42, 0.55)
        edge_actor.GetProperty().SetOpacity(0.5)
        renderer.AddActor(edge_actor)

        # Scalar bar
        title = {"tbv": "TBV", "inbreeding": "Inbreeding", "generation": "Generation"}.get(color_by, color_by)
        add_scalar_bar(renderer, title, lut)

        renderer.ResetCamera()
