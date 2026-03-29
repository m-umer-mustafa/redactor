import sys
import os
import multiprocessing

# 1. Natively patch Python's built-in multiprocessing for frozen Windows apps
if __name__ == '__main__':
    multiprocessing.freeze_support()

# 2. Prevent joblib/loky fork bomb (spaCy uses joblib which passes '-c' under the hood)
# PyInstaller ignores the '-c' flag, causing infinite recursions as it restarts the main script.
if len(sys.argv) >= 3 and sys.argv[1] == '-c':
    exec(sys.argv[2])
    sys.exit(0)

# 2.5 Prevent spacy utility sub-shelling (-m spacy)
if len(sys.argv) >= 3 and sys.argv[1] == '-m':
    sys.exit(0)

# 3. Aggressively disable multiprocessing environment variables for offline inference
os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.cpu_count = lambda: 1
multiprocessing.cpu_count = lambda: 1

import qdarktheme
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QStackedWidget, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
    QTextBrowser, QFileDialog, QMessageBox, QProgressDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QColor, QTextCharFormat, QTextCursor

from ui_components import DragDropDropzone, EntityListItem
from audit import AuditLogger

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Redactor — Sensitive Data Shield")
        self.setGeometry(100, 100, 1300, 850)
        
        # Set Application Icon if exists
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.audit_logger = AuditLogger()
        self.current_file = None
        self.current_snippets = []
        self.approved_entities = set()
        
        # Central widget is a stacked widget to switch between dropzone and review
        self.stacked = QStackedWidget()
        self.setCentralWidget(self.stacked)
        
        # Page 1: Dropzone
        self.dropzone_page = QWidget()
        dz_layout = QVBoxLayout()
        dz_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dropzone = DragDropDropzone()
        self.dropzone.setFixedSize(600, 400)
        self.dropzone.fileDropped.connect(self.process_file)
        dz_layout.addWidget(self.dropzone)
        self.dropzone_page.setLayout(dz_layout)
        
        # Page 2: Review & Confirm UI
        self.review_page = QWidget()
        rv_layout = QVBoxLayout()
        rv_layout.setContentsMargins(20, 20, 20, 20)
        rv_layout.setSpacing(15)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.lbl_filename = QLabel("No file loaded")
        self.lbl_filename.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        self.lbl_filename.setStyleSheet("color: white;")
        toolbar.addWidget(self.lbl_filename)
        toolbar.addStretch()
        
        self.btn_export = QPushButton("Apply Redactions & Export Document")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #007BFF;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 12px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.btn_export.clicked.connect(self.export_document)
        toolbar.addWidget(self.btn_export)
        
        rv_layout.addLayout(toolbar)
        
        # Splitter for Document and Entities
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(10)
        
        # Text Browser for document preview
        self.text_browser = QTextBrowser()
        self.text_browser.setFont(QFont("Segoe UI", 12))
        self.text_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #1e1e1e;
                padding: 30px;
                border: 1px solid #333;
                border-radius: 8px;
            }
        """)
        self.splitter.addWidget(self.text_browser)
        
        # Entity List
        self.entity_list = QListWidget()
        self.entity_list.setMaximumWidth(450)
        self.entity_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.entity_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1c;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #252526;
                border-radius: 6px;
                margin-bottom: 5px;
            }
            QListWidget::item:selected {
                background-color: #2d2d30;
                border: 1px solid #007BFF;
            }
            QScrollBar:vertical {
                border: none;
                background: #1e1e1e;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                min-height: 20px;
                border-radius: 5px;
            }
        """)
        self.splitter.addWidget(self.entity_list)
        
        # Ratios
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)
        
        rv_layout.addWidget(self.splitter)
        self.review_page.setLayout(rv_layout)
        
        # Add pages
        self.stacked.addWidget(self.dropzone_page)
        self.stacked.addWidget(self.review_page)
        
    def process_file(self, file_path: str):
        self.current_file = file_path
        self.lbl_filename.setText(f"Reviewing: {os.path.basename(file_path)}")
        self.approved_entities.clear()
        
        # Loading Dialog
        self.progress = QProgressDialog("Loading and Analyzing...", None, 0, 0, self)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.show()
        
        # Start Worker
        from worker import MLWorker
        self.worker = MLWorker(file_path)
        self.worker.progress.connect(self.progress.setLabelText)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()

    def on_analysis_finished(self, raw_text: str, snippets: list, filename: str):
        self.progress.close()
        self.current_snippets = snippets
        
        # Populate text browser
        self.text_browser.setPlainText(raw_text)
        
        # Highlight entities
        cursor = self.text_browser.textCursor()
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#E26868")) # Red-ish highlight
        highlight_format.setForeground(QColor("#FFFFFF"))
        
        self.entity_list.clear()
        # Sort snippets descending so replacements/highlights don't offset indices
        for s in sorted(snippets, key=lambda x: x['start'], reverse=True):
            cursor.setPosition(s['start'])
            cursor.setPosition(s['end'], QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(highlight_format)
            
            # Auto-approve all initially
            self.approved_entities.add(s['text'])
            
        # Deselect cursor
        cursor.clearSelection()
        self.text_browser.setTextCursor(cursor)
        
        # Populate entity list
        # Build UI list ascending
        unique_texts = set()
        for s in sorted(snippets, key=lambda x: x['start']):
            # For simplicity in MVP, we track unique textual strings instead of index-exact replacements
            if s['text'] in unique_texts:
                continue
            unique_texts.add(s['text'])
            
            item = QListWidgetItem(self.entity_list)
            widget = EntityListItem(0, s)
            widget.statusChanged.connect(self.update_approval_status)
            item.setSizeHint(widget.sizeHint())
            self.entity_list.setItemWidget(item, widget)
            
        self.stacked.setCurrentWidget(self.review_page)
        
    def on_analysis_error(self, err_msg: str):
        self.progress.close()
        QMessageBox.critical(self, "Error", f"An error occurred: {err_msg}")
        self.stacked.setCurrentWidget(self.dropzone_page)

    def update_approval_status(self, is_approved: bool, text: str):
        if is_approved:
            self.approved_entities.add(text)
        else:
            self.approved_entities.discard(text)

    def export_document(self):
        if not self.current_file:
            return
            
        suggested_name = os.path.basename(self.current_file)
        name, ext = os.path.splitext(suggested_name)
        new_name = f"{name}_REDACTED{ext}"
        
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Redacted Document", new_name, f"{ext.upper()} Files (*{ext})"
        )
        
        if output_path:
            self.btn_export.setText("Applying Redactions...")
            self.btn_export.setEnabled(False)
            
            from redactor import Redactor
            success = Redactor.redact(self.current_file, output_path, list(self.approved_entities))
            
            if success:
                # Log to audit trail
                actions = []
                for s in self.current_snippets:
                    status = "APPROVED" if s['text'] in self.approved_entities else "REJECTED"
                    actions.append({
                        "entity_text": s['text'],
                        "type": s['entity_type'],
                        "action": status
                    })
                
                # We use the system username as reviewer id
                reviewer = os.getlogin() if hasattr(os, 'getlogin') else "UnknownUser"
                self.audit_logger.append_entry(os.path.basename(self.current_file), reviewer, actions)
                
                QMessageBox.information(self, "Success", f"Document successfully redacted and saved to:\n{output_path}\n\nAudit log updated.")
                self.stacked.setCurrentWidget(self.dropzone_page)
            else:
                QMessageBox.critical(self, "Error", "Failed to apply redactions. See console logs.")
                
            self.btn_export.setText("Apply Redactions & Export")
            self.btn_export.setEnabled(True)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    # Optional PyInstaller multiprocess environment overrides for spaCy/joblib
    os.environ["LOKY_MAX_CPU_COUNT"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarktheme.load_stylesheet("dark")) # Modern dark theme for AI tools
    
    font = QFont("Inter", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
