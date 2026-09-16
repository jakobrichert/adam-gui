"""VTK scene rendered offscreen and blitted into an ordinary QWidget.

``QVTKRenderWindowInteractor`` embeds a native OpenGL window, which hangs on
macOS with Qt 6 + VTK 9.4+ and cannot be overlaid with normal widgets or
captured with ``QWidget.grab()``. Rendering offscreen and painting the pixels
ourselves avoids all three problems; a full HiDPI frame is ~5-10 ms.
"""

from __future__ import annotations

import numpy as np

import vtkmodules.vtkInteractionStyle  # noqa: F401  (registers interactor styles)
import vtkmodules.vtkRenderingFreeType  # noqa: F401  (text rendering)
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401  (OpenGL backend)
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow
from vtkmodules.vtkRenderingUI import vtkGenericRenderWindowInteractor

from adam_gui.qt_compat import (
    QColor, QEvent, QImage, QPainter, QPoint, QPointF, QSizePolicy, Qt, QTimer,
    QWidget, Signal,
)
from adam_gui.themes import palette, theme

_CLICK_SLOP = 4  # logical px a press may move and still count as a click


class VTKCanvas(QWidget):
    """Interactive VTK viewport.

    Signals:
        clicked(x, y): display coordinates in VTK convention (origin bottom-left,
            physical pixels) of a left click that was not a drag.
        hovered(x, y): same convention, emitted on mouse move when hover
            tracking is enabled via ``set_hover_tracking(True)``.
        rendered(): after every frame.
    """

    clicked = Signal(int, int)
    hovered = Signal(int, int)
    rendered = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 200)

        self.render_window = vtkRenderWindow()
        self.render_window.SetOffScreenRendering(1)
        self.renderer = vtkRenderer()
        self.renderer.SetUseFXAA(True)
        self.render_window.AddRenderer(self.renderer)

        self.interactor = vtkGenericRenderWindowInteractor()
        self.interactor.SetRenderWindow(self.render_window)
        self.style = vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(self.style)
        self.interactor.Initialize()

        self.render_window.AddObserver("EndEvent", self._on_vtk_render_end)

        self._image: QImage | None = None
        self._pending = False
        self._in_grab = False
        self._press_pos: QPoint | None = None
        self._hover = False
        self._buttons_down = 0
        # Optional callable used by the R key; defaults to the iso preset.
        self.home_view = None

        theme().changed.connect(self.apply_theme)
        self.apply_theme()

    # ------------------------------------------------------------ appearance
    def apply_theme(self, *_):
        p = palette()
        self.renderer.GradientBackgroundOn()
        self.renderer.SetBackground(*p.qcolor_tuple(p.scene_bg))
        self.renderer.SetBackground2(*p.qcolor_tuple(p.scene_bg_2))
        self.request_render()

    def set_hover_tracking(self, on: bool):
        self._hover = on
        self.setMouseTracking(on)

    # ------------------------------------------------------------ rendering
    def _scale(self) -> float:
        return float(self.devicePixelRatioF())

    def _pixel_size(self) -> tuple[int, int]:
        s = self._scale()
        return max(1, int(round(self.width() * s))), max(1, int(round(self.height() * s)))

    def request_render(self):
        """Schedule a render on the next event-loop turn (coalesced)."""
        if not self._pending:
            self._pending = True
            QTimer.singleShot(0, self._do_render)

    def render_now(self):
        self._pending = False
        self._sync_size()
        self.render_window.Render()

    def _do_render(self):
        self._pending = False
        if not self.isVisible():
            return
        self.render_now()

    def _sync_size(self):
        w, h = self._pixel_size()
        if tuple(self.render_window.GetSize()) != (w, h):
            self.render_window.SetSize(w, h)
            self.interactor.SetSize(w, h)
            self.render_window.SetDPI(int(round(72 * self._scale())))

    def _on_vtk_render_end(self, *_):
        if self._in_grab:
            return
        self._in_grab = True
        try:
            self._image = self._read_pixels()
        finally:
            self._in_grab = False
        self.update()
        self.rendered.emit()

    def _read_pixels(self) -> QImage:
        w, h = self.render_window.GetSize()
        arr = vtkUnsignedCharArray()
        self.render_window.GetRGBACharPixelData(0, 0, w - 1, h - 1, 0, arr)
        data = vtk_to_numpy(arr).reshape(h, w, 4)[::-1]
        data = np.ascontiguousarray(data)
        img = QImage(data.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
        img.setDevicePixelRatio(self._scale())
        return img

    def grab_image(self) -> QImage:
        """Render and return the current frame (physical resolution)."""
        self.render_now()
        return self._image.copy() if self._image is not None else QImage()

    def save_image(self, path: str) -> bool:
        return self.grab_image().save(path)

    def paintEvent(self, _event):
        painter = QPainter(self)
        if self._image is not None and not self._image.isNull():
            painter.drawImage(QPointF(0, 0), self._image)
            # Fill any gap while a resize is pending
            iw = self._image.width() / self._image.devicePixelRatio()
            ih = self._image.height() / self._image.devicePixelRatio()
            if iw < self.width() or ih < self.height():
                bg = QColor(palette().scene_bg)
                painter.fillRect(int(iw), 0, self.width(), self.height(), bg)
                painter.fillRect(0, int(ih), self.width(), self.height(), bg)
        else:
            painter.fillRect(self.rect(), QColor(palette().scene_bg))
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_size()
        self.interactor.ConfigureEvent()
        self.request_render()

    def showEvent(self, event):
        super().showEvent(event)
        self.request_render()

    # ------------------------------------------------------------ camera
    def reset_camera(self):
        self.renderer.ResetCamera()
        self.renderer.ResetCameraClippingRange()
        self.request_render()

    def set_view(self, preset: str = "iso"):
        """Camera presets; scenes use +Y as 'up'."""
        cam = self.renderer.GetActiveCamera()
        bounds = self.renderer.ComputeVisiblePropBounds()
        if bounds[0] > bounds[1]:
            return
        cx, cy, cz = ((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2, (bounds[4] + bounds[5]) / 2)
        cam.SetFocalPoint(cx, cy, cz)
        directions = {
            "front": ((0, 0, 1), (0, 1, 0)),
            "side": ((1, 0, 0), (0, 1, 0)),
            "top": ((0, 1, 0), (0, 0, -1)),
            "iso": ((0.55, 0.45, 0.70), (0, 1, 0)),
        }
        (dx, dy, dz), up = directions.get(preset, directions["iso"])
        cam.SetPosition(cx + dx, cy + dy, cz + dz)
        cam.SetViewUp(*up)
        self.renderer.ResetCamera()
        cam.Zoom(1.15)
        self.renderer.ResetCameraClippingRange()
        self.request_render()

    # ------------------------------------------------------------ input
    def _event_xy(self, pos: QPointF) -> tuple[int, int]:
        s = self._scale()
        return int(pos.x() * s), int(pos.y() * s)

    def _set_event_info(self, event, repeat: int = 0):
        x, y = self._event_xy(event.position())
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier) or bool(mods & Qt.KeyboardModifier.MetaModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self.interactor.SetEventInformationFlipY(x, y, int(ctrl), int(shift), chr(0), repeat)

    def vtk_display_pos(self, pos: QPointF) -> tuple[int, int]:
        x, y = self._event_xy(pos)
        return x, self._pixel_size()[1] - y - 1

    def mousePressEvent(self, event):
        self.setFocus()
        self._sync_size()
        self._set_event_info(event, 1 if event.type() == QEvent.Type.MouseButtonDblClick else 0)
        btn = event.button()
        self._buttons_down += 1
        if btn == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self.interactor.LeftButtonPressEvent()
        elif btn == Qt.MouseButton.RightButton:
            self.interactor.RightButtonPressEvent()
        elif btn == Qt.MouseButton.MiddleButton:
            self.interactor.MiddleButtonPressEvent()

    def mouseDoubleClickEvent(self, event):
        self.mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._set_event_info(event)
        btn = event.button()
        self._buttons_down = max(0, self._buttons_down - 1)
        if btn == Qt.MouseButton.LeftButton:
            self.interactor.LeftButtonReleaseEvent()
            if self._press_pos is not None:
                delta = event.position().toPoint() - self._press_pos
                if abs(delta.x()) + abs(delta.y()) <= _CLICK_SLOP:
                    x, y = self.vtk_display_pos(event.position())
                    self.clicked.emit(x, y)
            self._press_pos = None
        elif btn == Qt.MouseButton.RightButton:
            self.interactor.RightButtonReleaseEvent()
        elif btn == Qt.MouseButton.MiddleButton:
            self.interactor.MiddleButtonReleaseEvent()

    def mouseMoveEvent(self, event):
        self._set_event_info(event)
        if self._buttons_down:
            self.interactor.MouseMoveEvent()
        elif self._hover:
            x, y = self.vtk_display_pos(event.position())
            self.hovered.emit(x, y)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y() * 4
        if delta == 0:
            return
        self._set_event_info(event)
        self.style.SetMouseWheelMotionFactor(min(3.0, max(0.05, abs(delta) / 120.0)))
        if delta > 0:
            self.interactor.MouseWheelForwardEvent()
        else:
            self.interactor.MouseWheelBackwardEvent()
        event.accept()

    def event(self, event):
        if event.type() == QEvent.Type.NativeGesture:
            gtype = event.gestureType()
            if gtype == Qt.NativeGestureType.ZoomNativeGesture:
                cam = self.renderer.GetActiveCamera()
                cam.Dolly(1.0 + float(event.value()))
                self.renderer.ResetCameraClippingRange()
                self.request_render()
                return True
            if gtype == Qt.NativeGestureType.RotateNativeGesture:
                self.renderer.GetActiveCamera().Roll(-float(event.value()))
                self.request_render()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_R:
            if callable(self.home_view):
                self.home_view()
            else:
                self.set_view("iso")
        elif key == Qt.Key.Key_F:
            self.set_view("front")
        elif key == Qt.Key.Key_T:
            self.set_view("top")
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.render_window.Finalize()
        super().closeEvent(event)
