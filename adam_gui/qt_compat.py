"""Qt compatibility shim - supports both PyQt6 and PySide6."""

try:
    from PyQt6.QtWidgets import *  # noqa: F401, F403
    from PyQt6.QtCore import *  # noqa: F401, F403
    from PyQt6.QtGui import *  # noqa: F401, F403
    from PyQt6.QtSvg import QSvgRenderer  # noqa: F401
    from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, pyqtProperty as Property  # noqa: F401
    QT_BINDING = "PyQt6"
    BINDING_VERSION = PYQT_VERSION_STR  # noqa: F405
except ImportError:
    from PySide6.QtWidgets import *  # noqa: F401, F403
    from PySide6.QtCore import *  # noqa: F401, F403
    from PySide6.QtGui import *  # noqa: F401, F403
    from PySide6.QtSvg import QSvgRenderer  # noqa: F401
    from PySide6.QtCore import Signal, Slot, Property  # noqa: F401
    QT_BINDING = "PySide6"
    import PySide6 as _pyside
    BINDING_VERSION = _pyside.__version__
    QT_VERSION_STR = qVersion()  # noqa: F405
