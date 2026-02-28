"""3D chromosome/karyogram visualization pipeline."""

import math
import numpy as np

from vtkmodules.vtkCommonCore import vtkPoints, vtkFloatArray
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkFiltersSources import vtkCylinderSource, vtkSphereSource
from vtkmodules.vtkFiltersCore import vtkGlyph3D, vtkAppendPolyData
from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

from adam_gui.vtk_pipelines.common import make_diverging_lut, add_scalar_bar
from adam_gui.models.parameters import ChromosomeSpec
from adam_gui.models.results import QTLInfo


class ChromosomePipeline:
    """Build a 3D chromosome karyogram with QTL markers."""

    def build(
        self,
        renderer: vtkRenderer,
        chromosomes: list[ChromosomeSpec],
        qtl_info: list[QTLInfo],
        generation: int = 0,
    ):
        renderer.RemoveAllViewProps()

        n_chrom = len(chromosomes)
        if n_chrom == 0:
            return

        append = vtkAppendPolyData()

        # Arrange chromosomes in a row
        spacing = 4.0
        max_len = max(c.length_cm for c in chromosomes) if chromosomes else 100

        for i, chrom in enumerate(chromosomes):
            # Cylinder for chromosome body
            cyl = vtkCylinderSource()
            cyl.SetRadius(0.8)
            cyl.SetHeight(chrom.length_cm / max_len * 20.0)
            cyl.SetResolution(20)
            cyl.Update()

            # Transform to position
            transform = vtkTransform()
            transform.Translate(i * spacing - (n_chrom - 1) * spacing / 2, 0, 0)

            tf = vtkTransformPolyDataFilter()
            tf.SetInputConnection(cyl.GetOutputPort())
            tf.SetTransform(transform)
            tf.Update()

            append.AddInputData(tf.GetOutput())

        append.Update()

        chrom_mapper = vtkPolyDataMapper()
        chrom_mapper.SetInputConnection(append.GetOutputPort())

        chrom_actor = vtkActor()
        chrom_actor.SetMapper(chrom_mapper)
        chrom_actor.GetProperty().SetColor(0.3, 0.35, 0.5)
        chrom_actor.GetProperty().SetOpacity(0.6)
        renderer.AddActor(chrom_actor)

        # QTL markers
        if qtl_info:
            qtl_points = vtkPoints()
            effect_scalars = vtkFloatArray()
            effect_scalars.SetName("Effect")
            size_scalars = vtkFloatArray()
            size_scalars.SetName("Size")

            for qtl in qtl_info:
                if qtl.chromosome >= n_chrom:
                    continue
                chrom = chromosomes[qtl.chromosome]
                x = qtl.chromosome * spacing - (n_chrom - 1) * spacing / 2
                y = (qtl.position_cm / max(chrom.length_cm, 1) - 0.5) * (chrom.length_cm / max_len * 20.0)
                z = 1.5  # Offset from chromosome body

                qtl_points.InsertNextPoint(x, y, z)
                effect = qtl.allele_effects[0] if qtl.allele_effects else 0.0
                effect_scalars.InsertNextValue(effect)
                size_scalars.InsertNextValue(min(1.0, abs(effect) * 2 + 0.2))

            qtl_pd = vtkPolyData()
            qtl_pd.SetPoints(qtl_points)
            qtl_pd.GetPointData().AddArray(effect_scalars)
            qtl_pd.GetPointData().AddArray(size_scalars)
            qtl_pd.GetPointData().SetActiveScalars("Size")

            sphere = vtkSphereSource()
            sphere.SetRadius(1.0)
            sphere.SetPhiResolution(10)
            sphere.SetThetaResolution(10)

            glyph = vtkGlyph3D()
            glyph.SetInputData(qtl_pd)
            glyph.SetSourceConnection(sphere.GetOutputPort())
            glyph.SetScaleModeToScaleByScalar()
            glyph.SetScaleFactor(0.5)

            qtl_pd.GetPointData().SetActiveScalars("Effect")

            lut = make_diverging_lut()
            sr = effect_scalars.GetRange()
            # Symmetrize around 0
            abs_max = max(abs(sr[0]), abs(sr[1]), 0.01)
            lut.SetTableRange(-abs_max, abs_max)

            qtl_mapper = vtkPolyDataMapper()
            qtl_mapper.SetInputConnection(glyph.GetOutputPort())
            qtl_mapper.SetLookupTable(lut)
            qtl_mapper.SetScalarRange(-abs_max, abs_max)

            qtl_actor = vtkActor()
            qtl_actor.SetMapper(qtl_mapper)
            renderer.AddActor(qtl_actor)

            add_scalar_bar(renderer, "QTL Effect", lut)

        # Add chromosome labels
        from vtkmodules.vtkRenderingCore import vtkTextActor
        for i in range(n_chrom):
            label = vtkTextActor()
            label.SetInput(f"Chr {i + 1}")
            label.GetTextProperty().SetColor(0.65, 0.67, 0.76)
            label.GetTextProperty().SetFontSize(14)
            label.GetPositionCoordinate().SetCoordinateSystemToWorld()
            x = i * spacing - (n_chrom - 1) * spacing / 2
            label.GetPositionCoordinate().SetValue(x - 0.8, -12, 0)
            renderer.AddActor2D(label)

        renderer.ResetCamera()
