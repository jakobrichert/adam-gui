"""VTK render window embedded in Qt."""

from adam_gui.qt_compat import QWidget, QVBoxLayout

import vtkmodules.vtkRenderingOpenGL2  # noqa: F401 - required for OpenGL rendering
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkRenderingCore import vtkRenderer


class VTKWidget(QWidget):
    """QVTKRenderWindowInteractor wrapper for embedding VTK in PyQt."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self.vtk_widget)

        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.12, 0.12, 0.15)
        self.renderer.SetBackground2(0.05, 0.05, 0.08)
        self.renderer.GradientBackgroundOn()

        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()

    def start(self):
        """Initialize the interactor (call after widget is shown)."""
        self.interactor.Initialize()

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()

    def reset_camera(self):
        self.renderer.ResetCamera()
        self.render()

    def clear(self):
        self.renderer.RemoveAllViewProps()
        self.render()

    def closeEvent(self, event):
        self.vtk_widget.close()
        super().closeEvent(event)
