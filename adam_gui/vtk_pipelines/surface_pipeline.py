"""3D genetic gain landscape surface visualization pipeline."""

import numpy as np

from vtkmodules.vtkCommonCore import vtkPoints, vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkStructuredGrid
from vtkmodules.vtkRenderingCore import vtkActor, vtkDataSetMapper, vtkRenderer, vtkProperty
from vtkmodules.vtkFiltersCore import vtkContourFilter

from adam_gui.vtk_pipelines.common import make_diverging_lut, add_scalar_bar
from adam_gui.models.results import SimulationResults


class SurfacePipeline:
    """Build a 3D surface plot of breeding metrics over generations."""

    def build_single_run(
        self,
        renderer: vtkRenderer,
        results: SimulationResults,
        metric: str = "mean_tbv",
        trait_index: int = 0,
        show_contours: bool = True,
    ):
        """Build surface from a single run with replicates on Y axis."""
        renderer.RemoveAllViewProps()

        if not results.generations:
            return

        gens = sorted(results.generations, key=lambda g: g.generation)
        n_gens = len(gens)

        # For single run, create a band showing the metric with
        # a synthetic Y dimension based on variance
        n_y = 20
        points = vtkPoints()
        scalars = vtkFloatArray()
        scalars.SetName(metric)

        for j in range(n_y):
            for i, g in enumerate(gens):
                x = float(g.generation)
                y = (j - n_y / 2) * 0.5

                val = getattr(g, metric, None)
                if val is None:
                    z_center = 0.0
                elif isinstance(val, list):
                    z_center = val[trait_index] if trait_index < len(val) else 0.0
                else:
                    z_center = float(val)

                # Add Gaussian shape across Y for visual effect
                y_norm = (j - n_y / 2) / (n_y / 4)
                z = z_center * np.exp(-0.5 * y_norm ** 2)

                points.InsertNextPoint(x, y, z)
                scalars.InsertNextValue(z)

        grid = vtkStructuredGrid()
        grid.SetDimensions(n_gens, n_y, 1)
        grid.SetPoints(points)
        grid.GetPointData().SetScalars(scalars)

        # Surface
        lut = make_diverging_lut()
        lut.SetTableRange(scalars.GetRange())

        mapper = vtkDataSetMapper()
        mapper.SetInputData(grid)
        mapper.SetLookupTable(lut)
        mapper.SetScalarRange(scalars.GetRange())

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetOpacity(0.85)
        renderer.AddActor(actor)

        # Wireframe overlay
        wire_mapper = vtkDataSetMapper()
        wire_mapper.SetInputData(grid)
        wire_mapper.ScalarVisibilityOff()

        wire_actor = vtkActor()
        wire_actor.SetMapper(wire_mapper)
        wire_actor.GetProperty().SetRepresentationToWireframe()
        wire_actor.GetProperty().SetColor(0.5, 0.52, 0.65)
        wire_actor.GetProperty().SetOpacity(0.3)
        wire_actor.GetProperty().SetLineWidth(1)
        renderer.AddActor(wire_actor)

        # Contour lines
        if show_contours:
            contour = vtkContourFilter()
            contour.SetInputData(grid)
            sr = scalars.GetRange()
            n_contours = 8
            for i in range(n_contours):
                val = sr[0] + (sr[1] - sr[0]) * (i + 1) / (n_contours + 1)
                contour.SetValue(i, val)

            contour_mapper = vtkDataSetMapper()
            contour_mapper.SetInputConnection(contour.GetOutputPort())
            contour_mapper.ScalarVisibilityOff()

            contour_actor = vtkActor()
            contour_actor.SetMapper(contour_mapper)
            contour_actor.GetProperty().SetColor(0.8, 0.84, 0.96)
            contour_actor.GetProperty().SetLineWidth(2)
            renderer.AddActor(contour_actor)

        metric_title = metric.replace("_", " ").title()
        add_scalar_bar(renderer, metric_title, lut)

        renderer.ResetCamera()

    def build_comparison(
        self,
        renderer: vtkRenderer,
        runs: list[SimulationResults],
        metric: str = "mean_tbv",
        trait_index: int = 0,
    ):
        """Build surface comparing multiple runs."""
        renderer.RemoveAllViewProps()

        if not runs:
            return

        n_runs = len(runs)
        max_gens = max(r.n_generations for r in runs)

        points = vtkPoints()
        scalars = vtkFloatArray()
        scalars.SetName(metric)

        for run_idx, results in enumerate(runs):
            gens = sorted(results.generations, key=lambda g: g.generation)
            for gen_idx in range(max_gens):
                x = float(gen_idx)
                y = float(run_idx) * 3.0

                if gen_idx < len(gens):
                    g = gens[gen_idx]
                    val = getattr(g, metric, None)
                    if val is None:
                        z = 0.0
                    elif isinstance(val, list):
                        z = val[trait_index] if trait_index < len(val) else 0.0
                    else:
                        z = float(val)
                else:
                    z = 0.0

                points.InsertNextPoint(x, y, z)
                scalars.InsertNextValue(z)

        grid = vtkStructuredGrid()
        grid.SetDimensions(max_gens, n_runs, 1)
        grid.SetPoints(points)
        grid.GetPointData().SetScalars(scalars)

        lut = make_diverging_lut()
        lut.SetTableRange(scalars.GetRange())

        mapper = vtkDataSetMapper()
        mapper.SetInputData(grid)
        mapper.SetLookupTable(lut)
        mapper.SetScalarRange(scalars.GetRange())

        actor = vtkActor()
        actor.SetMapper(mapper)
        renderer.AddActor(actor)

        add_scalar_bar(renderer, metric.replace("_", " ").title(), lut)
        renderer.ResetCamera()
