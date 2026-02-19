from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class GlowButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._glow_strength = 0.0

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setOffset(0, 0)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(84, 224, 255, 0))
        self.setGraphicsEffect(self._shadow)

        self._animation = QPropertyAnimation(self, b"glowStrength")
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    @Property(float)
    def glowStrength(self) -> float:
        return self._glow_strength

    @glowStrength.setter
    def glowStrength(self, value: float) -> None:
        self._glow_strength = value
        alpha = int(120 * value)
        self._shadow.setBlurRadius(2 + 22 * value)
        self._shadow.setColor(QColor(84, 224, 255, alpha))

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._animation.stop()
        self._animation.setStartValue(self.glowStrength)
        self._animation.setEndValue(1.0)
        self._animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._animation.stop()
        self._animation.setStartValue(self.glowStrength)
        self._animation.setEndValue(0.0)
        self._animation.start()
        super().leaveEvent(event)


class NotificationBellButton(GlowButton):
    def __init__(self, icon: QIcon | None = None, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setObjectName("notificationBellButton")
        self.setFixedSize(44, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Notifications")
        self.setAccessibleName("Update Notifications")

        if icon and not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(20, 20))
        else:
            self.setText("N")

        self._badge = QLabel(self)
        self._badge.setObjectName("notificationBadge")
        self._badge.setFixedSize(12, 12)
        self._badge.hide()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._badge.move(self.width() - self._badge.width() - 5, 4)

    def set_has_notification(self, has_notification: bool) -> None:
        self._badge.setVisible(has_notification)

    def has_notification(self) -> bool:
        return self._badge.isVisible()


class DropZoneWidget(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragOver", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        title = QLabel("Drop audio or video files here")
        title.setObjectName("dropZoneTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Supports mp3, wav, mp4, and most other media formats")
        subtitle.setObjectName("dropZoneSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

    def _set_drag_state(self, active: bool) -> None:
        self.setProperty("dragOver", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_state(True)
            return
        event.ignore()

    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._set_drag_state(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_state(False)
        urls = event.mimeData().urls()
        files = [str(Path(url.toLocalFile())) for url in urls if url.isLocalFile()]
        if files:
            self.files_dropped.emit(files)
            event.acceptProposedAction()
            return
        event.ignore()
