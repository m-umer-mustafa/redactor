import os

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MultiFileDropZone(QFrame):
    filesDropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropzone")
        self._reset_style()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Drop Files To Start Batch")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #f0f0f0;")

        subtitle = QLabel("Supports multiple PDF and DOCX files")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Inter", 11))
        subtitle.setStyleSheet("color: #9aa0a6;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

    def _reset_style(self):
        self.setStyleSheet(
            """
            #dropzone {
                border: 2px dashed #4e4e50;
                border-radius: 14px;
                background-color: #1e1e1e;
                padding: 32px;
            }
            """
        )

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        files = [u.toLocalFile() for u in event.mimeData().urls()]
        accepted = [f for f in files if os.path.isfile(f) and f.lower().endswith((".pdf", ".docx"))]
        if accepted:
            self.setStyleSheet(
                """
                #dropzone {
                    border: 2px solid #2e7dff;
                    border-radius: 14px;
                    background-color: #172036;
                    padding: 32px;
                }
                """
            )
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, _event):
        self._reset_style()

    def dropEvent(self, event):
        self._reset_style()
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        accepted = [f for f in files if os.path.isfile(f) and f.lower().endswith((".pdf", ".docx"))]
        if accepted:
            self.filesDropped.emit(accepted)
            event.acceptProposedAction()
            return
        event.ignore()


class RowActionWidget(QWidget):
    cancelRequested = pyqtSignal(str)
    reviewRequested = pyqtSignal(str)

    def __init__(self, file_id: str):
        super().__init__()
        self.file_id = file_id

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.review_btn = QPushButton("Review")
        self.review_btn.setVisible(False)
        self.review_btn.clicked.connect(lambda: self.reviewRequested.emit(self.file_id))

        self.cancel_btn = QPushButton("X")
        self.cancel_btn.setFixedWidth(28)
        self.cancel_btn.clicked.connect(lambda: self.cancelRequested.emit(self.file_id))

        layout.addWidget(self.review_btn)
        layout.addWidget(self.cancel_btn)

    def set_review_visible(self, visible: bool):
        self.review_btn.setVisible(visible)

    def set_cancel_enabled(self, enabled: bool):
        self.cancel_btn.setEnabled(enabled)


class ToastNotification(QWidget):
    """
    Frameless toast that slides in and fades out automatically.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        shell = QFrame(self)
        shell.setObjectName("toastShell")
        shell.setStyleSheet(
            """
            #toastShell {
                background-color: rgba(24, 24, 26, 235);
                border: 1px solid #3f3f46;
                border-radius: 10px;
            }
            """
        )

        self.label = QLabel("")
        self.label.setStyleSheet("color: #f5f5f5; padding: 10px 14px;")

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.addWidget(self.label)
        wrapper.addWidget(shell)

        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.opacity.setOpacity(0.0)

        self.slide_anim = QPropertyAnimation(self, b"pos", self)
        self.slide_anim.setDuration(220)
        self.slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.fade_anim = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade_anim.setDuration(280)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.hide()

    def show_toast(self, message: str, duration_ms: int = 3000):
        self.label.setText(message)
        self.adjustSize()

        parent = self.parentWidget()
        if parent is None:
            return

        end_x = parent.width() - self.width() - 24
        end_y = parent.height() - self.height() - 24
        start = QPoint(parent.width() + 10, end_y)
        end = QPoint(end_x, end_y)

        self.move(start)
        self.show()
        self.raise_()

        self.slide_anim.stop()
        self.slide_anim.setStartValue(start)
        self.slide_anim.setEndValue(end)
        self.slide_anim.start()

        self.fade_anim.stop()
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self):
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.opacity.opacity())
        self.fade_anim.setEndValue(0.0)
        try:
            self.fade_anim.finished.disconnect(self.hide)
        except TypeError:
            pass
        self.fade_anim.finished.connect(self.hide)
        self.fade_anim.start()


class BackgroundProgressBanner(QFrame):
    """
    Small persistent banner shown when processing continues in background.
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("progressBanner")
        self.setStyleSheet(
            """
            #progressBanner {
                background-color: #1d273f;
                border: 1px solid #3b5998;
                border-radius: 10px;
                padding: 6px 12px;
            }
            QLabel {
                color: #dbe7ff;
            }
            """
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 6, 10, 6)
        self.label = QLabel("No active jobs")
        row.addWidget(self.label)
        self.hide()

    def update_text(self, text: str):
        self.label.setText(text)
