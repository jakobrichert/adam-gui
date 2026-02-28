"""3D PCA scatter plot visualization pipeline."""

import numpy as np

from vtkmodules.vtkCommonCore import vtkPoints, vtkFloatArray, vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersSources import vtkSphereSource
from vtkmodules.vtkFiltersCore import vtkGlyph3D
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.vtk_pipelines.common import make_rainbow_lut, make_diverging_lut, add_scalar_bar


class ScatterPipeline:
    """Build a 3D PCA scatter plot from pre-computed PC coordinates."""

    def build(
        self,
        renderer: vtkRenderer,
        pc_coords: dict[int, np.ndarray],  # gen -> (n_ind, 3)
        metadata: dict[int, dict] | None = None,  # gen -> {"tbv": array, "selected": array}
        color_by: str = "generation",
    ):
        renderer.RemoveAllViewProps()

        if not pc_coords:
            return

        all_gens = sorted(pc_coords.keys())
        n_total = sum(arr.shape[0] for arr in pc_coords.values())

        points = vtkPoints()
        scalars = vtkFloatArray()
        scalars.SetName(color_by)
        sizes = vtkFloatArray()
        sizes.SetName("Size")

        for gen in all_gens:
            coords = pc_coords[gen]
            n = coords.shape[0]
            meta = metadata.get(gen, {}) if metadata else {}
            tbvs = meta.get("tbv", np.zeros(n))
            selected = meta.get("selected", np.ones(n, dtype=bool))

            for i in range(n):
                points.InsertNextPoint(float(coords[i, 0]), float(coords[i, 1]), float(coords[i, 2]))

                if color_by == "generation":
                    scalars.InsertNextValue(float(gen))
                elif color_by == "tbv":
                    scalars.InsertNextValue(float(tbvs[i]) if i < len(tbvs) else 0.0)
                else:
                    scalars.InsertNextValue(float(gen))

                sz = 0.4 if (i < len(selected) and selected[i]) else 0.2
                sizes.InsertNextValue(sz)

        pd = vtkPolyData()
        pd.SetPoints(points)
        pd.GetPointData().AddArray(scalars)
        pd.GetPointData().AddArray(sizes)
        pd.GetPointData().SetActiveScalars("Size")

        # Glyph
        sphere = vtkSphereSource()
        sphere.SetRadius(1.0)
        sphere.SetPhiResolution(8)
        sphere.SetThetaResolution(8)

        glyph = vtkGlyph3D()
        glyph.SetInputData(pd)
        glyph.SetSourceConnection(sphere.GetOutputPort())
        glyph.SetScaleModeToScaleByScalar()
        glyph.SetScaleFactor(1.0)

        pd.GetPointData().SetActiveScalars(color_by)

        # LUT
        if color_by == "generation":
            lut = make_rainbow_lut()
            lut.SetTableRange(min(all_gens), max(all_gens))
        else:
            lut = make_diverging_lut()
            lut.SetTableRange(scalars.GetRange())

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(glyph.GetOutputPort())
        mapper.SetLookupTable(lut)
        mapper.SetScalarRange(scalars.GetRange())

        actor = vtkActor()
        actor.SetMapper(mapper)
        renderer.AddActor(actor)

        # Population centroids per generation
        for gen in all_gens:
            coords = pc_coords[gen]
            centroid = coords.mean(axis=0)

            centroid_sphere = vtkSphereSource()
            centroid_sphere.SetCenter(*centroid)
            centroid_sphere.SetRadius(0.8)
            centroid_sphere.SetPhiResolution(16)
            centroid_sphere.SetThetaResolution(16)

            c_mapper = vtkPolyDataMapper()
            c_mapper.SetInputConnection(centroid_sphere.GetOutputPort())

            c_actor = vtkActor()
            c_actor.SetMapper(c_mapper)

            # Color centroid by generation
            t = (gen - min(all_gens)) / max(1, max(all_gens) - min(all_gens))
            c_actor.GetProperty().SetColor(0.3 + 0.7 * t, 0.5, 1.0 - 0.7 * t)
            c_actor.GetProperty().SetOpacity(0.4)
            renderer.AddActor(c_actor)

        title = {"generation": "Generation", "tbv": "TBV"}.get(color_by, color_by)
        add_scalar_bar(renderer, title, lut)

        renderer.ResetCamera()
