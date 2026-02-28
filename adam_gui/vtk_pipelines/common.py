"""Shared VTK pipeline utilities and base class."""

from vtkmodules.vtkRenderingCore import (
    vtkRenderer, vtkActor, vtkPolyDataMapper,
)
from vtkmodules.vtkRenderingAnnotation import (
    vtkCubeAxesActor, vtkScalarBarActor,
)
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonCore import vtkLookupTable, vtkFloatArray


def make_diverging_lut(n_colors: int = 256, low_rgb=(0.23, 0.35, 0.98), high_rgb=(0.95, 0.55, 0.66)):
    """Create a diverging color lookup table (blue to red through white)."""
    lut = vtkLookupTable()
    lut.SetNumberOfTableValues(n_colors)
    lut.Build()
    mid = n_colors // 2
    for i in range(n_colors):
        if i < mid:
            t = i / mid
            r = low_rgb[0] + t * (1.0 - low_rgb[0])
            g = low_rgb[1] + t * (1.0 - low_rgb[1])
            b = low_rgb[2] + t * (1.0 - low_rgb[2])
        else:
            t = (i - mid) / (n_colors - mid)
            r = 1.0 + t * (high_rgb[0] - 1.0)
            g = 1.0 + t * (high_rgb[1] - 1.0)
            b = 1.0 + t * (high_rgb[2] - 1.0)
        lut.SetTableValue(i, r, g, b, 1.0)
    return lut


def make_rainbow_lut(n_colors: int = 256):
    """Create a rainbow lookup table for generation coloring."""
    lut = vtkLookupTable()
    lut.SetHueRange(0.6, 0.0)  # Blue to red
    lut.SetSaturationRange(0.8, 0.8)
    lut.SetValueRange(0.9, 0.9)
    lut.SetNumberOfTableValues(n_colors)
    lut.Build()
    return lut


def make_categorical_lut(n_categories: int = 10):
    """Create a categorical color lookup table."""
    colors = [
        (0.54, 0.71, 0.98),  # Blue
        (0.65, 0.89, 0.63),  # Green
        (0.98, 0.70, 0.53),  # Peach
        (0.95, 0.55, 0.66),  # Red
        (0.80, 0.65, 0.97),  # Mauve
        (0.98, 0.89, 0.69),  # Yellow
        (0.58, 0.89, 0.83),  # Teal
        (0.95, 0.80, 0.80),  # Flamingo
        (0.46, 0.78, 0.93),  # Sapphire
        (0.71, 0.75, 1.00),  # Lavender
    ]
    lut = vtkLookupTable()
    lut.SetNumberOfTableValues(n_categories)
    for i in range(n_categories):
        c = colors[i % len(colors)]
        lut.SetTableValue(i, c[0], c[1], c[2], 1.0)
    lut.Build()
    return lut


def add_scalar_bar(renderer: vtkRenderer, title: str, lut: vtkLookupTable):
    """Add a color scalar bar to the renderer."""
    bar = vtkScalarBarActor()
    bar.SetLookupTable(lut)
    bar.SetTitle(title)
    bar.SetNumberOfLabels(5)
    bar.SetWidth(0.08)
    bar.SetHeight(0.4)
    bar.SetPosition(0.9, 0.3)
    bar.GetTitleTextProperty().SetColor(0.8, 0.84, 0.96)
    bar.GetTitleTextProperty().SetFontSize(12)
    bar.GetLabelTextProperty().SetColor(0.8, 0.84, 0.96)
    renderer.AddActor2D(bar)
    return bar


def add_axes(renderer: vtkRenderer, labels=("X", "Y", "Z"), bounds=None):
    """Add cube axes to the renderer."""
    axes = vtkCubeAxesActor()
    axes.SetCamera(renderer.GetActiveCamera())
    if bounds:
        axes.SetBounds(*bounds)

    axes.SetXTitle(labels[0])
    axes.SetYTitle(labels[1])
    axes.SetZTitle(labels[2])

    for prop_fn in [axes.GetTitleTextProperty, axes.GetLabelTextProperty]:
        for i in range(3):
            prop = prop_fn(i)
            prop.SetColor(0.65, 0.67, 0.76)
            prop.SetFontSize(10)

    axes.SetFlyModeToStaticTriad()
    axes.SetGridLineLocation(axes.VTK_GRID_LINES_FURTHEST)

    for fn in [axes.GetXAxesGridlinesProperty, axes.GetYAxesGridlinesProperty, axes.GetZAxesGridlinesProperty]:
        fn().SetColor(0.19, 0.19, 0.27)

    renderer.AddActor(axes)
    return axes
