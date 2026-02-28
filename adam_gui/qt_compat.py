"""Qt compatibility shim - supports both PyQt6 and PySide6."""

try:
    from PyQt6.QtWidgets import *  # noqa: F401, F403
    from PyQt6.QtCore import *  # noqa: F401, F403
    from PyQt6.QtGui import *  # noqa: F401, F403
    from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, pyqtProperty as Property  # noqa: F401
    QT_BINDING = "PyQt6"
except ImportError:
    from PySide6.QtWidgets import *  # noqa: F401, F403
    from PySide6.QtCore import *  # noqa: F401, F403
    from PySide6.QtGui import *  # noqa: F401, F403
    from PySide6.QtCore import Signal, Slot, Property  # noqa: F401
    QT_BINDING = "PySide6"
