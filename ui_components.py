import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QPushButton, QHBoxLayout, QFrame, QTextBrowser
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

class DragDropDropzone(QFrame):
    fileDropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropzone")
        self.setStyleSheet("""
            #dropzone {
                border: 2px dashed #4e4e50;
                border-radius: 12px;
                background-color: #1e1e1e;
                margin: 40px;
            }
            #dropzone:hover {
                border-color: #007BFF;
                background-color: #252526;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.icon_label = QLabel("☁️")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFont(QFont("Inter", 48))
        layout.addWidget(self.icon_label)
        
        self.label = QLabel("Drag & Drop your Legal Document")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        self.label.setStyleSheet("color: #e0e0e0; margin-top: 10px;")
        layout.addWidget(self.label)
        
        self.sub_label = QLabel("Supports PDF and DOCX files")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setFont(QFont("Inter", 12))
        self.sub_label.setStyleSheet("color: #888888; font-style: italic;")
        layout.addWidget(self.sub_label)
        
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.pdf', '.docx')):
                event.acceptProposedAction()
                self.setStyleSheet("""
                    #dropzone {
                        border: 2px solid #007BFF;
                        border-radius: 12px;
                        background-color: #1a2333;
                        margin: 40px;
                    }
                """)
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            #dropzone {
                border: 2px dashed #4e4e50;
                border-radius: 12px;
                background-color: #1e1e1e;
                margin: 40px;
            }
            #dropzone:hover {
                border-color: #007BFF;
                background-color: #252526;
            }
        """)

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.fileDropped.emit(file_path)
                return

class EntityListItem(QWidget):
    statusChanged = pyqtSignal(bool, str)
    
    def __init__(self, index, snippet_data):
        super().__init__()
        self.snippet_data = snippet_data
        self.entity_text = snippet_data['text']
        self.entity_type = snippet_data['entity_type']
        self.is_approved = True
        
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 12, 15, 12)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.lbl_text = QLabel(f"<b>{self.entity_text}</b>")
        self.lbl_text.setFont(QFont("Inter", 11))
        self.lbl_text.setStyleSheet("color: #ff6b6b;") # Vibrant dangerous red
        info_layout.addWidget(self.lbl_text)
        
        self.lbl_type = QLabel(self.entity_type)
        self.lbl_type.setFont(QFont("Inter", 9))
        self.lbl_type.setStyleSheet("color: #888888; font-weight: 500;")
        info_layout.addWidget(self.lbl_type)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        self.btn_toggle = QPushButton("Reject")
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setFixedSize(80, 30)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: rgba(220, 53, 69, 0.1);
                color: #ff4d4d;
                border: 1px solid #ff4d4d;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(220, 53, 69, 0.2);
            }
            QPushButton:checked {
                background-color: rgba(40, 167, 69, 0.1);
                color: #28a745;
                border: 1px solid #28a745;
            }
            QPushButton:checked:hover {
                background-color: rgba(40, 167, 69, 0.2);
            }
        """)
        self.btn_toggle.toggled.connect(self._on_toggled)
        layout.addWidget(self.btn_toggle)
        
        self.setLayout(layout)

    def _on_toggled(self, checked):
        if checked:
            self.btn_toggle.setText("Restore")
            self.is_approved = False
            self.lbl_text.setStyleSheet("color: #666666; text-decoration: line-through;")
            self.statusChanged.emit(False, self.entity_text)
        else:
            self.btn_toggle.setText("Reject")
            self.is_approved = True
            self.lbl_text.setStyleSheet("color: #ff6b6b;")
            self.statusChanged.emit(True, self.entity_text)
