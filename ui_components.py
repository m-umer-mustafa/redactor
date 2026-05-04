import os

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, pyqtSignal, QRect, QRectF
from PyQt6.QtGui import QFont, QPainter, QColor, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QDialog,
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
    browseRequested = pyqtSignal()

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

        subtitle = QLabel("Supports multiple PDF and DOCX files")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #94A3B8; margin-bottom: 8px;")
        subtitle.setFont(QFont("Inter", 11))

        self.browse_btn = QPushButton("Or Browse Files...")
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.setStyleSheet("padding: 8px 16px; border-radius: 6px; background-color: palette(button); color: palette(button-text); margin-top: 10px; max-width: 200px;")
        self.browse_btn.clicked.connect(self.browseRequested.emit)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _reset_style(self):
        self.setStyleSheet(
            """
            #dropzone {
                border: 2px dashed #334155;
                border-radius: 16px;
                background-color: rgba(30, 41, 59, 0.4);
                padding: 32px;
            }
            QLabel {
                background: transparent;
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
                    border: 2px dashed #3B82F6;
                    border-radius: 16px;
                    background-color: rgba(59, 130, 246, 0.1);
                    padding: 32px;
                }
                QLabel {
                    background: transparent;
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

        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setFixedWidth(28)
        self.cancel_btn.setStyleSheet("background-color: transparent; color: #EF4444; font-weight: bold; border-radius: 4px; padding: 4px;")
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
                background-color: #1E3A8A;
                border: 1px solid #3B82F6;
                border-radius: 10px;
                padding: 6px 12px;
            }
            QLabel {
                color: #DBEAFE;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-weight: 500;
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


class WalkthroughOverlay(QWidget):
    completed = pyqtSignal()
    
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.target_widget = None
        self.message = ""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.tooltip = QFrame(self)
        self.tooltip.setStyleSheet("""
            QFrame {
                background-color: #1E293B;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            QLabel {
                color: #F8FAFC;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 15px;
                border: none;
                padding: 12px;
                background: transparent;
            }
            QPushButton {
                background-color: #3B82F6;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 13px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        vbox = QVBoxLayout(self.tooltip)
        
        self.lbl_msg = QLabel()
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setMinimumWidth(250)
        vbox.addWidget(self.lbl_msg)
        
        btn_layout = QHBoxLayout()
        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.on_next)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_next)
        vbox.addLayout(btn_layout)
        
        self.tooltip.hide()
        self.hide()

    def set_target(self, widget: QWidget, message: str, btn_text: str = "Next"):
        self.target_widget = widget
        self.lbl_msg.setText(message)
        self.btn_next.setText(btn_text)
        
        # Resize to cover the parent window
        if self.parentWidget():
            self.resize(self.parentWidget().size())
        
        if self.target_widget:
            target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(target_global)
            
            self.tooltip.adjustSize()
            tt_w = self.tooltip.width()
            tt_h = self.tooltip.height()
            
            x = local_pos.x() + (self.target_widget.width() - tt_w) // 2
            y = local_pos.y() + self.target_widget.height() + 15
            
            if x < 10: x = 10
            if x + tt_w > self.width() - 10: x = self.width() - tt_w - 10
            if y + tt_h > self.height() - 10: y = local_pos.y() - tt_h - 10
            
            self.tooltip.move(x, y)
            self.tooltip.show()
        else:
            # If no target, center the tooltip
            self.tooltip.adjustSize()
            self.tooltip.move((self.width() - self.tooltip.width()) // 2, (self.height() - self.tooltip.height()) // 2)
            self.tooltip.show()
            
        self.show()
        self.raise_()
        self.update()

    def on_next(self):
        self.completed.emit()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create a full screen path
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        
        if self.target_widget and self.target_widget.isVisible():
            target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(target_global)
            rect = QRect(local_pos, self.target_widget.size())
            rect.adjust(-3, -3, 3, 3)
            
            # Subtract the hole from the dark overlay
            hole = QPainterPath()
            hole.addRoundedRect(QRectF(rect), 10, 10)
            path = path.subtracted(hole)
            
            # Fill the overlay (dimming effect)
            painter.fillPath(path, QColor(0, 0, 0, 180))
            
            # Draw modern glowing highlight
            pen = QPen(QColor("#3B82F6"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRoundedRect(QRectF(rect), 10, 10)
            
            # Outer subtle glow
            glow_pen = QPen(QColor(59, 130, 246, 60))
            glow_pen.setWidth(6)
            painter.setPen(glow_pen)
            painter.drawRoundedRect(QRectF(rect), 10, 10)
        else:
            painter.fillPath(path, QColor(0, 0, 0, 180))
            
    def mousePressEvent(self, event):
        if self.target_widget:
            target_global = self.target_widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(target_global)
            rect = QRect(local_pos, self.target_widget.size())
            rect.adjust(-6, -6, 6, 6)
            
            # If clicking inside the cutout, we want the button to actually be clicked!
            if rect.contains(event.pos()):
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                # We repost the event to the application so the button actually receives it
                # It's cleaner to let the user click the actual button and then we advance the walkthrough.
                event.ignore()
                return
                
        # Eat the event if clicking on the dark mask
        event.accept()

    def mouseReleaseEvent(self, event):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        event.ignore()

