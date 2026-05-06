import datetime
import json
import os
import sys
import uuid
import multiprocessing

import qdarktheme
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool, QUrl, QTimer
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QColor, QTextCursor, QTextCharFormat, QDesktopServices, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QCheckBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QScrollArea,
    QSlider,
    QComboBox,
    QGridLayout,
    QTextEdit,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QDialog,
    QMessageBox,
)

from audit import AuditLogger, delete_history_entries, clear_all_history, DEFAULT_LOG_FILE
from analytics import AnalyticsClient, get_analytics
from ui_components import (
    BackgroundProgressBanner,
    MultiFileDropZone,
    RowActionWidget,
    ToastNotification,
    WalkthroughOverlay,
)
from worker import RedactionWorker, ApplyRedactionWorker
from licensing import LicenseManager


if __name__ == "__main__":
    multiprocessing.freeze_support()

if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    exec(sys.argv[2])
    sys.exit(0)

if len(sys.argv) >= 3 and sys.argv[1] == "-m":
    sys.exit(0)

os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["LOKY_MAX_CPU_COUNT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.cpu_count = lambda: 1
multiprocessing.cpu_count = lambda: 1


class AppConfig:
    def __init__(self, path: str = None):
        if path is None:
            if os.path.exists("config.json"):
                path = "config.json"
            else:
                if sys.platform == "win32":
                    base = os.environ.get("APPDATA") or os.path.expanduser("~")
                elif sys.platform == "darwin":
                    base = os.path.expanduser("~/Library/Application Support")
                else:
                    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
                app_dir = os.path.join(base, "Redactor")
                os.makedirs(app_dir, exist_ok=True)
                path = os.path.join(app_dir, "config.json")
        self.path = path
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    self.data = json.load(f)
                except json.JSONDecodeError:
                    self.data = {}
        else:
            self.data = {}

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def user_name(self) -> str:
        return self.data.get("user_name", "").strip()

    def set_user_name(self, name: str):
        self.data["user_name"] = name.strip()
        self.save()

    @staticmethod
    def _fallback_export_path() -> str:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        if os.path.isdir(docs):
            return os.path.join(docs, "Redacted_Exports")
        return os.path.join(os.getcwd(), "Redacted_Exports")

    def default_export_path(self) -> str:
        path = self.data.get("default_export_path", "").strip()
        if not path:
            path = self._fallback_export_path()
            self.data["default_export_path"] = path
            self.save()
        return path

    def set_default_export_path(self, path: str):
        self.data["default_export_path"] = path.strip()
        self.save()

    def ensure_defaults(self):
        defaults = {
            "default_export_path": self._fallback_export_path(),
            "confidence_threshold": 0.6,
            "target_entities": [
                "PERSON",
                "LOCATION",
                "ORGANIZATION",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "US_SSN",
            ],
            "custom_allow_list": [],
            "redaction_style": "[REDACTED]",
            "file_suffix": "_REDACTED",
            "max_concurrent_files": 2,
            "license_key": "",
            "license_tier": "Free",
            "activation_token": ""
        }
        changed = False
        for key, value in defaults.items():
            if key not in self.data:
                self.data[key] = value
                changed = True
        if changed:
            self.save()

    def get_setting(self, key: str, default=None):
        return self.data.get(key, default)

    def update_settings(self, values: dict):
        self.data.update(values)
        self.save()

    def has_cumulative_dashboard_counters(self) -> bool:
        keys = ["total_files_redacted", "total_approved", "total_rejected"]
        return any(key in self.data for key in keys)

    def reset_dashboard_counters(self) -> None:
        self.data["total_files_redacted"] = 0
        self.data["total_approved"] = 0
        self.data["total_rejected"] = 0
        self.save()


class SidebarButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding: 12px 16px;
                border-radius: 8px;
                color: #94A3B8;
                background-color: transparent;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 500;
                border: none;
            }
            QPushButton:checked {
                background-color: rgba(59, 130, 246, 0.15);
                color: #3B82F6;
                font-weight: 600;
            }
            QPushButton:hover:!checked {
                background-color: rgba(255, 255, 255, 0.05);
                color: #F8FAFC;
            }
            """
        )


class LicenseDialog(QDialog):
    def __init__(self, current_tier="Free", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Unlock Professional Features")
        self.setFixedWidth(450)
        self.license_manager = LicenseManager()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Activate Your License")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel(
            "Redactor Solo and Pro features require an active license.\n"
            "Please enter your key below to unlock the application."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #94A3B8;")
        layout.addWidget(desc)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setStyleSheet(
            "padding: 10px; border: 1px solid #334155; border-radius: 6px; background: #0F172A;"
        )
        layout.addWidget(self.key_input)

        self.btn_activate = QPushButton("Activate Pro Features")
        self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_activate.setStyleSheet(
            "padding: 12px; background-color: #3B82F6; color: white; font-weight: 600; border-radius: 6px;"
        )
        self.btn_activate.clicked.connect(self.handle_activation)
        layout.addWidget(self.btn_activate)

        buy_label = QLabel("<a href='https://theredactor.netlify.app/#pricing' style='color: #3B82F6; text-decoration: none;'>Don't have a key? Buy one here.</a>")
        buy_label.setOpenExternalLinks(True)
        buy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(buy_label)

    def handle_activation(self):
        key = self.key_input.text().strip()
        if not key:
            return

        success, tier, message = self.license_manager.activate_online(key)
        
        if success:
            QMessageBox.information(self, "Success", message)
            self.tier = tier
            self.license_key = key
            self.accept()
        else:
            QMessageBox.warning(self, "Activation Failed", message)


class OnboardingPage(QWidget):
    completed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(14)

        title = QLabel("Welcome to The Redactor")
        title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        subtitle = QLabel("Everything runs locally on your device. Enter your name to continue.")
        subtitle.setStyleSheet("color: #a0a0a8;")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Your name")
        self.name_input.setMaximumWidth(420)

        save_btn = QPushButton("Continue")
        save_btn.setMaximumWidth(180)
        save_btn.clicked.connect(self._submit)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.name_input)
        layout.addWidget(save_btn)
        layout.addStretch()

    def _submit(self):
        name = self.name_input.text().strip()
        if name:
            self.completed.emit(name)


class DashboardPage(QWidget):
    startBatchRequested = pyqtSignal()
    howItWorksRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(14)

        self.greeting = QLabel("Welcome back")
        self.greeting.setFont(QFont("Inter", 20, QFont.Weight.Bold))

        stats_row = QHBoxLayout()
        self.total_files = QLabel("Files Redacted: 0")
        self.total_approved = QLabel("Approved Items: 0")
        self.total_rejected = QLabel("Rejected Items: 0")
        for widget in (self.total_files, self.total_approved, self.total_rejected):
            panel = QFrame()
            panel.setStyleSheet(
                "background-color: #1A1D27; border: 1px solid #2A2F3D; border-radius: 12px; padding: 6px;"
            )
            p_layout = QVBoxLayout(panel)
            p_layout.addWidget(widget)
            stats_row.addWidget(panel)

        self.start_btn = QPushButton("Start New Batch")
        self.start_btn.clicked.connect(self.startBatchRequested.emit)
        
        self.how_btn = QPushButton("How It Works")
        self.how_btn.clicked.connect(self.howItWorksRequested.emit)
        self.how_btn.setStyleSheet("background-color: transparent; border: 1px solid #3B82F6; color: #3B82F6;")
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.how_btn)
        btn_layout.addStretch()

        layout.addWidget(self.greeting)
        layout.addLayout(stats_row)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def set_user(self, name: str):
        self.greeting.setText(f"Welcome back, {name}")

    def set_stats(self, files_redacted: int, approved: int, rejected: int):
        self.total_files.setText(f"Files Redacted: {files_redacted}")
        self.total_approved.setText(f"Approved Items: {approved}")
        self.total_rejected.setText(f"Rejected Items: {rejected}")


class BatchPage(QWidget):
    filesDropped = pyqtSignal(list)
    reviewRequested = pyqtSignal(str)
    cancelRequested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.dropzone = MultiFileDropZone()
        self.dropzone.filesDropped.connect(self.filesDropped.emit)
        self.dropzone.browseRequested.connect(self._browse_files)
        self.dropzone.setMinimumHeight(140)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Filename", "Status", "Progress", "Actions", "Path", "FileId"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(4, True)
        self.table.setColumnHidden(5, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.dropzone)
        layout.addWidget(self.table)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Documents",
            "",
            "Documents (*.pdf *.docx)"
        )
        if files:
            self.filesDropped.emit(files)

    def add_file_row(self, file_id: str, file_name: str, full_path: str):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(file_name))
        self.table.setItem(row, 1, QTableWidgetItem("Pending"))
        self.table.setItem(row, 2, QTableWidgetItem("0%"))

        action_widget = RowActionWidget(file_id)
        action_widget.reviewRequested.connect(self.reviewRequested.emit)
        action_widget.cancelRequested.connect(self.cancelRequested.emit)
        self.table.setCellWidget(row, 3, action_widget)

        self.table.setItem(row, 4, QTableWidgetItem(full_path))
        self.table.setItem(row, 5, QTableWidgetItem(file_id))
        return action_widget

    def _row_for_file_id(self, file_id: str) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 5)
            if item and item.text() == file_id:
                return row
        return -1

    def set_status(self, file_id: str, value: str):
        row = self._row_for_file_id(file_id)
        if row < 0:
            return
        status_item = self.table.item(row, 1)
        if status_item:
            status_item.setText(value)

    def set_progress(self, file_id: str, value: int):
        row = self._row_for_file_id(file_id)
        if row < 0:
            return
        progress_item = self.table.item(row, 2)
        if progress_item:
            progress_item.setText(f"{value}%")

    def remove_file_row(self, file_id: str):
        row = self._row_for_file_id(file_id)
        if row < 0:
            return
        action_widget = self.table.cellWidget(row, 3)
        if action_widget:
            action_widget.setParent(None)
            action_widget.deleteLater()
        self.table.removeRow(row)


class HistoryPage(QWidget):
    deleteSelectedRequested = pyqtSignal(list)
    clearAllRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._confirm_armed = {"clear_all": False}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by file name...")
        self.search_input.textChanged.connect(self._filter_rows)

        button_row = QHBoxLayout()
        self.btn_delete_selected = QPushButton("Delete Selected")
        self.btn_clear_all = QPushButton("Clear All History")

        self.btn_delete_selected.clicked.connect(self._request_delete_selected)
        self.btn_clear_all.clicked.connect(
            lambda: self._arm_or_execute_confirm(
                key="clear_all",
                button=self.btn_clear_all,
                default_text="Clear All History",
                action=self.clearAllRequested.emit,
            )
        )

        button_row.addWidget(self.btn_delete_selected)
        button_row.addWidget(self.btn_clear_all)
        button_row.addStretch()

        # 5 columns: Select (checkbox), File, Date, Words Redacted, Rejected Items
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Select", "File", "Date", "Words Redacted", "Rejected Items"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

        layout.addWidget(self.search_input)
        layout.addLayout(button_row)
        layout.addWidget(self.table)

    def _request_delete_selected(self):
        filenames = self.get_selected_filenames()
        if not filenames:
            return
        self.deleteSelectedRequested.emit(filenames)

    def _arm_or_execute_confirm(self, key: str, button: QPushButton, default_text: str, action):
        if self._confirm_armed.get(key, False):
            self._confirm_armed[key] = False
            self._reset_confirm_button(button, default_text)
            action()
            return

        self._confirm_armed[key] = True
        button.setText("Are you sure? Click again")
        button.setStyleSheet(
            "background-color: #8b1e1e; color: white; border: 1px solid #b33636; border-radius: 6px;"
        )

        QTimer.singleShot(3000, lambda: self._expire_confirm(key, button, default_text))

    def _expire_confirm(self, key: str, button: QPushButton, default_text: str):
        if not self._confirm_armed.get(key, False):
            return
        self._confirm_armed[key] = False
        self._reset_confirm_button(button, default_text)

    @staticmethod
    def _reset_confirm_button(button: QPushButton, default_text: str):
        button.setText(default_text)
        button.setStyleSheet("")

    def get_selected_filenames(self) -> list[str]:
        """Extract filenames from checked rows (column 0 has checkboxes)."""
        filenames = []
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.CheckState.Checked:
                # Filename is in column 1
                file_item = self.table.item(row, 1)
                if file_item:
                    filenames.append(file_item.text())
        return list(dict.fromkeys(filenames))

    def load_entries(self, entries: list):
        self.table.setRowCount(0)
        for row_data in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Column 0: Checkbox for row selection
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(checkbox_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, checkbox_item)

            # Column 1: File name
            self.table.setItem(row, 1, QTableWidgetItem(row_data["file"]))
            # Column 2: Date
            self.table.setItem(row, 2, QTableWidgetItem(row_data["date"]))
            # Column 3: Words Redacted
            self.table.setItem(row, 3, QTableWidgetItem(str(row_data["words_redacted"])))
            # Column 4: Rejected Items
            self.table.setItem(row, 4, QTableWidgetItem(str(row_data["rejected_items"])))

        self._filter_rows(self.search_input.text())

    def _filter_rows(self, query: str):
        term = query.strip().lower()
        for row in range(self.table.rowCount()):
            # File name is in column 1 now
            file_item = self.table.item(row, 1)
            file_name = file_item.text().lower() if file_item else ""
            hide = bool(term) and term not in file_name
            self.table.setRowHidden(row, hide)


class SettingsView(QWidget):
    browseRequested = pyqtSignal()
    openFolderRequested = pyqtSignal()
    settings_saved_signal = pyqtSignal(dict)
    statsResetRequested = pyqtSignal()
    allDataClearedRequested = pyqtSignal()

    ENTITY_CHOICES = [
        "PERSON",
        "LOCATION",
        "ORGANIZATION",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
    ]

    def __init__(self):
        super().__init__()
        self._confirm_armed = {
            "reset_stats": False,
            "clear_all_data": False,
        }

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        form = QVBoxLayout(body)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(14)

        title = QLabel("Settings")
        title.setFont(QFont("Inter", 18, QFont.Weight.Bold))
        form.addWidget(title)

        det_label = QLabel("Detection Engine Tuning")
        det_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        form.addWidget(det_label)

        # License Status Row
        status_row = QHBoxLayout()
        self.tier_badge = QLabel("FREE TIER")
        self.tier_badge.setStyleSheet(
            "padding: 4px 8px; background: #334155; color: #94A3B8; border-radius: 4px; font-weight: bold; font-size: 10px;"
        )
        status_row.addWidget(QLabel("Current Plan:"))
        status_row.addWidget(self.tier_badge)
        status_row.addStretch()
        form.addLayout(status_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Confidence Threshold"))
        self.threshold_value = QLabel("0.60")
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 100)
        self.threshold_slider.setValue(60)
        self.threshold_slider.valueChanged.connect(self._update_threshold_label)
        threshold_row.addWidget(self.threshold_slider, 1)
        threshold_row.addWidget(self.threshold_value)
        form.addLayout(threshold_row)

        form.addWidget(QLabel("Target Entities"))
        entity_grid = QGridLayout()
        self.entity_checks = {}
        pro_entities = {"US_SSN"}
        for idx, entity in enumerate(self.ENTITY_CHOICES):
            label_text = entity
            if entity in pro_entities:
                label_text += " (PRO)"
            cb = QCheckBox(label_text)
            cb.setChecked(True)
            self.entity_checks[entity] = cb
            entity_grid.addWidget(cb, idx // 3, idx % 3)
        form.addLayout(entity_grid)

        form.addWidget(QLabel("Custom Allow-List (comma separated)"))
        self.allow_list_edit = QTextEdit()
        self.allow_list_edit.setPlaceholderText("Example: Employer, Employee, Confidential Settlement and Release Agreement")
        self.allow_list_edit.setFixedHeight(90)
        form.addWidget(self.allow_list_edit)

        exp_label = QLabel("Export Preferences")
        exp_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        form.addWidget(exp_label)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(True)
        self.path_input.setPlaceholderText("No export folder selected")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browseRequested.emit)
        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self.openFolderRequested.emit)
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(browse_btn)
        path_row.addWidget(open_btn)
        form.addLayout(path_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("Redaction Style"))
        self.redaction_style_combo = QComboBox()
        self.redaction_style_combo.addItems(["[REDACTED]", "████████", "[PII_TYPE]"])
        style_row.addWidget(self.redaction_style_combo, 1)
        form.addLayout(style_row)

        suffix_row = QHBoxLayout()
        suffix_row.addWidget(QLabel("File Suffix"))
        self.file_suffix_input = QLineEdit("_REDACTED")
        suffix_row.addWidget(self.file_suffix_input, 1)
        form.addLayout(suffix_row)

        sys_label = QLabel("System & Performance")
        sys_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        form.addWidget(sys_label)

        threads_row = QHBoxLayout()
        threads_row.addWidget(QLabel("Max Concurrent Files (Threads)"))
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.thread_spin.setValue(2)
        threads_row.addWidget(self.thread_spin)
        form.addLayout(threads_row)

        self.save_btn = QPushButton("Apply & Save Settings")
        self.save_btn.clicked.connect(self._emit_saved_settings)
        form.addWidget(self.save_btn)

        # Data Management Section
        data_mgmt_label = QLabel("Data Management")
        data_mgmt_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        form.addWidget(data_mgmt_label)

        data_mgmt_row = QHBoxLayout()
        self.btn_reset_stats = QPushButton("Reset Dashboard Stats")
        self.btn_clear_all_data = QPushButton("Clear All App Data")

        self.btn_reset_stats.clicked.connect(
            lambda: self._arm_or_execute_confirm(
                key="reset_stats",
                button=self.btn_reset_stats,
                default_text="Reset Dashboard Stats",
                action=self.statsResetRequested.emit,
            )
        )
        self.btn_clear_all_data.clicked.connect(
            lambda: self._arm_or_execute_confirm(
                key="clear_all_data",
                button=self.btn_clear_all_data,
                default_text="Clear All App Data",
                action=self.allDataClearedRequested.emit,
            )
        )

        data_mgmt_row.addWidget(self.btn_reset_stats)
        data_mgmt_row.addWidget(self.btn_clear_all_data)
        data_mgmt_row.addStretch()
        form.addLayout(data_mgmt_row)

        form.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)

    def _update_threshold_label(self, _value: int = 0):
        self.threshold_value.setText(f"{self.threshold_slider.value() / 100:.2f}")

    def _emit_saved_settings(self):
        payload = self.collect_values()
        self.settings_saved_signal.emit(payload)

    def _arm_or_execute_confirm(self, key: str, button: QPushButton, default_text: str, action):
        if self._confirm_armed.get(key, False):
            self._confirm_armed[key] = False
            self._reset_confirm_button(button, default_text)
            action()
            return

        self._confirm_armed[key] = True
        button.setText("Are you sure? Click again")
        button.setStyleSheet(
            "background-color: #8b1e1e; color: white; border: 1px solid #b33636; border-radius: 6px;"
        )

        QTimer.singleShot(3000, lambda: self._expire_confirm(key, button, default_text))

    def _expire_confirm(self, key: str, button: QPushButton, default_text: str):
        if not self._confirm_armed.get(key, False):
            return
        self._confirm_armed[key] = False
        self._reset_confirm_button(button, default_text)

    @staticmethod
    def _reset_confirm_button(button: QPushButton, default_text: str):
        button.setText(default_text)
        button.setStyleSheet("")

    def collect_values(self) -> dict:
        checked_entities = [e for e, cb in self.entity_checks.items() if cb.isChecked()]
        allow_list = [x.strip() for x in self.allow_list_edit.toPlainText().split(",") if x.strip()]
        return {
            "confidence_threshold": round(self.threshold_slider.value() / 100.0, 2),
            "target_entities": checked_entities,
            "custom_allow_list": allow_list,
            "redaction_style": self.redaction_style_combo.currentText(),
            "file_suffix": self.file_suffix_input.text().strip() or "_REDACTED",
            "max_concurrent_files": int(self.thread_spin.value()),
            "default_export_path": self.path_input.text().strip(),
        }

    def set_export_path(self, path: str):
        self.path_input.setText(path)

    def load_from_config(self, config: AppConfig):
        self.path_input.setText(config.default_export_path())
        self.threshold_slider.setValue(int(float(config.get_setting("confidence_threshold", 0.6)) * 100))
        self._update_threshold_label()

        current_tier = config.get_setting("license_tier", "Free")
        self.tier_badge.setText(f"{current_tier.upper()} PLAN")
        if current_tier == "Free":
            self.tier_badge.setStyleSheet("padding: 4px 8px; background: #334155; color: #94A3B8; border-radius: 4px; font-weight: bold; font-size: 10px;")
        else:
            self.tier_badge.setStyleSheet("padding: 4px 8px; background: #1E3A8A; color: #3B82F6; border-radius: 4px; font-weight: bold; font-size: 10px;")

        selected_entities = set(config.get_setting("target_entities", self.ENTITY_CHOICES))
        pro_entities = {"US_SSN"}
        for entity, cb in self.entity_checks.items():
            cb.setChecked(entity in selected_entities)
            if entity in pro_entities and current_tier == "Free":
                cb.setEnabled(False)
                cb.setChecked(False)
                cb.setToolTip("Upgrade to Pro to unlock sensitive entity detection")
            else:
                cb.setEnabled(True)
                cb.setToolTip("")

        allow_list = config.get_setting("custom_allow_list", [])
        self.allow_list_edit.setPlainText(", ".join(allow_list))

        style = config.get_setting("redaction_style", "[REDACTED]")
        index = self.redaction_style_combo.findText(style)
        self.redaction_style_combo.setCurrentIndex(index if index >= 0 else 0)

        self.file_suffix_input.setText(config.get_setting("file_suffix", "_REDACTED"))

        max_threads = int(config.get_setting("max_concurrent_files", 2))
        self.thread_spin.setValue(max(1, min(max_threads, self.thread_spin.maximum())))




class ReviewPage(QWidget):
    previousRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    backRequested = pyqtSignal()
    applyCurrentRequested = pyqtSignal()
    applyAllRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._approved = set()
        self._snippets = []
        self._manual_snippets = {}  # Track manual additions by (start, end) tuple for easy removal

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.prev_btn = QPushButton("<")
        self.next_btn = QPushButton(">")
        self.context_label = QLabel("File 0 of 0")
        self.context_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.back_btn = QPushButton("Back to Batch Hub")

        self.prev_btn.clicked.connect(self.previousRequested.emit)
        self.next_btn.clicked.connect(self.nextRequested.emit)
        self.back_btn.clicked.connect(self.backRequested.emit)

        top.addWidget(self.prev_btn)
        top.addWidget(self.next_btn)
        top.addWidget(self.context_label)
        top.addWidget(self.back_btn)

        legend = QHBoxLayout()
        legend.setSpacing(10)

        approved_chip = QLabel("Approved for Redaction")
        approved_chip.setStyleSheet(
            "padding: 4px 10px; border-radius: 10px; "
            "background-color: #6f2d40; color: #ffeef2; border: 1px solid #a64764;"
        )

        rejected_chip = QLabel("Rejected (Keep)")
        rejected_chip.setStyleSheet(
            "padding: 4px 10px; border-radius: 10px; "
            "background-color: #2f4a39; color: #e7f6eb; border: 1px solid #4f7d61;"
        )

        legend.addWidget(approved_chip)
        legend.addWidget(rejected_chip)
        legend.addStretch()

        body = QHBoxLayout()

        # Use QTextEdit instead of QTextBrowser to enable context menu
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_preview.customContextMenuRequested.connect(self._show_context_menu)

        self.entity_list = QListWidget()
        self.entity_list.itemChanged.connect(self._on_item_changed)
        self.entity_list.setMaximumWidth(420)

        body.addWidget(self.text_preview)
        body.addWidget(self.entity_list)

        actions = QHBoxLayout()
        self.apply_current_btn = QPushButton("Apply & Save Current")
        self.apply_all_btn = QPushButton("Apply All Approved in Batch")
        self.apply_current_btn.clicked.connect(self.applyCurrentRequested.emit)
        self.apply_all_btn.clicked.connect(self.applyAllRequested.emit)
        actions.addWidget(self.apply_current_btn)
        actions.addWidget(self.apply_all_btn)
        actions.addStretch()

        root.addLayout(top)
        root.addLayout(legend)
        root.addLayout(body)
        root.addLayout(actions)

    def set_context(self, index_1_based: int, total: int, file_name: str):
        self.context_label.setText(f"File {index_1_based} of {total}  |  {file_name}")

    def load_document(self, raw_text: str, snippets: list, approved_entities: set):
        self._approved = set(approved_entities)
        self._snippets = list(snippets)
        self._manual_snippets = {}  # Reset manual additions when loading new document
        self.text_preview.setPlainText(raw_text)
        self._refresh_entity_list()
        self._apply_highlighting()

    def _refresh_entity_list(self):
        """Rebuild entity list with sections for AI-detected and Manual Additions."""
        self.entity_list.blockSignals(True)
        self.entity_list.clear()

        # Section 1: AI-Detected Entities
        if self._snippets:
            section_item = QListWidgetItem("━━ AI-DETECTED ━━")
            section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            section_item.setForeground(QColor("#888888"))
            font = section_item.font()
            font.setBold(True)
            section_item.setFont(font)
            self.entity_list.addItem(section_item)

            seen = set()
            for snippet in self._snippets:
                txt = snippet.get("text", "")
                if not txt or txt in seen:
                    continue
                seen.add(txt)

                display_text = f"{txt}  [{snippet.get('entity_type', 'UNKNOWN')}]"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, txt)
                item.setData(Qt.ItemDataRole.UserRole + 1, "ai")  # Mark as AI-detected
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if txt in self._approved else Qt.CheckState.Unchecked)
                self.entity_list.addItem(item)

        # Section 2: Manual Additions
        if self._manual_snippets:
            section_item = QListWidgetItem("━━ MANUAL ADDITIONS ━━")
            section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            section_item.setForeground(QColor("#d4a574"))
            font = section_item.font()
            font.setBold(True)
            section_item.setFont(font)
            self.entity_list.addItem(section_item)

            for (start, end), snippet in self._manual_snippets.items():
                txt = snippet.get("text", "")
                display_text = f"{txt}  [MANUAL] ✕"
                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, txt)
                item.setData(Qt.ItemDataRole.UserRole + 1, "manual")  # Mark as manual
                item.setData(Qt.ItemDataRole.UserRole + 2, (start, end))  # Store position for removal
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if txt in self._approved else Qt.CheckState.Unchecked)
                self.entity_list.addItem(item)

        self.entity_list.blockSignals(False)

    def _on_item_changed(self, item: QListWidgetItem):
        entity = item.data(Qt.ItemDataRole.UserRole)
        item_type = item.data(Qt.ItemDataRole.UserRole + 1)  # "ai" or "manual"

        # Handle manual removal: right-click or double-click on manual item with ✕
        if item_type == "manual" and item.checkState() == Qt.CheckState.Unchecked:
            pos_tuple = item.data(Qt.ItemDataRole.UserRole + 2)
            if pos_tuple in self._manual_snippets:
                del self._manual_snippets[pos_tuple]
                self._refresh_entity_list()
                self._apply_highlighting()
                return

        # Standard approve/reject logic
        if item.checkState() == Qt.CheckState.Checked:
            self._approved.add(entity)
        else:
            self._approved.discard(entity)
        self._apply_highlighting()

    def _show_context_menu(self, position):
        """Display context menu with 'Mark Selected Text for Redaction' option."""
        # Check if there is selected text (BEFORE moving cursor, which would clear selection)
        cursor = self.text_preview.textCursor()
        if not cursor.hasSelection():
            return  # No selection, don't show menu

        menu = QMenu(self)
        mark_action = QAction("Mark Selected Text for Redaction", self)
        mark_action.triggered.connect(self._mark_selected_for_redaction)
        menu.addAction(mark_action)

        # Show menu at cursor position
        menu.exec(self.text_preview.mapToGlobal(position))

    def _mark_selected_for_redaction(self):
        """Capture selected text and add as a manual redaction entity."""
        cursor = self.text_preview.textCursor()
        if not cursor.hasSelection():
            return

        selected_text = cursor.selectedText()
        start_pos = cursor.selectionStart()
        end_pos = cursor.selectionEnd()

        if not selected_text or len(selected_text) == 0:
            return

        # Create manual entity dictionary (mimics presidio RecognizerResult structure)
        manual_entity = {
            "text": selected_text,
            "entity_type": "MANUAL_REDACTION",
            "start": start_pos,
            "end": end_pos,
            "score": 1.0,
            "approved": True,
        }

        # Store in manual snippets tracker using (start, end) as unique key
        self._manual_snippets[(start_pos, end_pos)] = manual_entity

        # Automatically approve the manual entity
        self._approved.add(selected_text)

        # Add to main snippets list so it gets highlighted
        self._snippets.append(manual_entity)

        # Refresh UI
        self._refresh_entity_list()
        self._apply_highlighting()

        # Clear selection so user can see the highlight applied
        cursor.clearSelection()
        self.text_preview.setTextCursor(cursor)

    def _apply_highlighting(self):
        """Apply approved/rejected background colors based on snippet positions."""
        doc = self.text_preview.document()
        if doc is None:
            return

        approved_format = QTextCharFormat()
        approved_format.setBackground(QColor("#6f2d40"))
        approved_format.setForeground(QColor("#ffeef2"))

        rejected_format = QTextCharFormat()
        rejected_format.setBackground(QColor("#2f4a39"))
        rejected_format.setForeground(QColor("#e7f6eb"))

        clear_format = QTextCharFormat()
        clear_format.setBackground(QColor("transparent"))

        reset_cursor = QTextCursor(doc)
        reset_cursor.setPosition(0)
        reset_cursor.setPosition(len(doc.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
        reset_cursor.setCharFormat(clear_format)

        for snippet in sorted(self._snippets, key=lambda s: s.get("start", 0), reverse=True):
            start = snippet.get("start", None)
            end = snippet.get("end", None)
            text = snippet.get("text", "")
            if start is None or end is None:
                continue
            if not isinstance(start, int) or not isinstance(end, int):
                continue
            if end <= start:
                continue

            cursor = QTextCursor(doc)
            cursor.setPosition(max(0, start))
            cursor.setPosition(min(len(doc.toPlainText()), end), QTextCursor.MoveMode.KeepAnchor)
            if text in self._approved:
                cursor.setCharFormat(approved_format)
            else:
                cursor.setCharFormat(rejected_format)

    def approved_entities(self) -> set:
        return set(self._approved)


class MainWindow(QMainWindow):
    PAGE_ONBOARDING = 0
    PAGE_DASHBOARD = 1
    PAGE_BATCH = 2
    PAGE_HISTORY = 3
    PAGE_REVIEW = 4
    PAGE_SETTINGS = 5

    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Redactor v0.1.2 (Stable)")
        self.setMinimumSize(800, 600)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_responsive_window_geometry()

        self.config = AppConfig()
        self.audit_logger = AuditLogger()
        self.config.ensure_defaults()

        # ── Analytics: initialise with credentials from config.json ──
        # Add "ga4_measurement_id" and "ga4_api_secret" to config.json to activate.
        # A persistent anonymous client_id is stored so sessions can be linked.
        ga4_client_id = self.config.get_setting("ga4_client_id")
        if not ga4_client_id:
            ga4_client_id = str(uuid.uuid4())
            self.config.update_settings({"ga4_client_id": ga4_client_id})
        AnalyticsClient.initialise(
            measurement_id=self.config.get_setting("ga4_measurement_id", "G-XXXXXXXXXX"),
            api_secret=self.config.get_setting("ga4_api_secret", "YOUR_API_SECRET"),
            client_id=ga4_client_id,
            mixpanel_token=self.config.get_setting("mixpanel_token"),
        )
        get_analytics().app_opened()

        self.batch_items = {}
        self.batch_order = []
        self.current_review_id = None
        self.redaction_workers = {}
        self.threadpool = QThreadPool()
        # Keep this low because en_core_web_lg + Presidio are memory-heavy.
        self.threadpool.setMaxThreadCount(2)

        self.toast = ToastNotification(self)

        self.walkthrough_overlay = WalkthroughOverlay(self)
        self.walkthrough_step = 0

        root = QWidget()
        self.setCentralWidget(root)
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        main_layout.addWidget(self.sidebar)

        content_shell = QWidget()
        content_layout = QVBoxLayout(content_shell)
        content_layout.setContentsMargins(14, 14, 14, 14)

        self.banner = BackgroundProgressBanner()
        content_layout.addWidget(self.banner)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_shell, 1)

        self.onboarding_page = OnboardingPage()
        self.dashboard_page = DashboardPage()
        self.batch_page = BatchPage()
        self.history_page = HistoryPage()
        self.review_page = ReviewPage()
        self.settings_page = SettingsView()

        self.stack.addWidget(self.onboarding_page)
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.batch_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.review_page)
        self.stack.addWidget(self.settings_page)

        self._wire_events()
        self.settings_page.load_from_config(self.config)
        self._apply_performance_settings_from_config()
        self._route_initial_page()
        self._refresh_dashboard_stats()

    def showEvent(self, event):
        super().showEvent(event)
        # Force license check on startup for Paid-Only model
        if self.config.get_setting("license_tier", "Free") == "Free":
            self.show_license_dialog()

    def show_license_dialog(self):
        dialog = LicenseDialog(self.config.get_setting("license_tier", "Free"), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config.update_settings({
                "license_key": dialog.license_key,
                "license_tier": dialog.tier
            })
            self.toast.show_toast(f"Plan Activated: {dialog.tier}")
            if self.stack.currentIndex() == self.PAGE_SETTINGS:
                self.settings_page.load_from_config(self.config)
        else:
            # Hard Lock: Exit if no license is provided
            sys.exit(0)

    def _setup_responsive_window_geometry(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1100, 760)
            return

        available = screen.availableGeometry()
        target_w = max(800, int(available.width() * 0.7))
        target_h = max(600, int(available.height() * 0.7))
        self.resize(target_w, target_h)

        x = available.x() + (available.width() - target_w) // 2
        y = available.y() + (available.height() - target_h) // 2
        self.move(x, y)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setFixedWidth(230)
        panel.setStyleSheet("background-color: #13161F; border-right: 1px solid #202432;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(8)

        brand = QLabel("THE REDACTOR")
        brand.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        brand.setStyleSheet("color: #f4f4f5;")

        self.btn_dashboard = SidebarButton("Dashboard")
        self.btn_batch = SidebarButton("Batch Redaction")
        self.btn_history = SidebarButton("History")
        self.btn_settings = SidebarButton("Settings")

        layout.addWidget(brand)
        layout.addSpacing(18)
        layout.addWidget(self.btn_dashboard)
        layout.addWidget(self.btn_batch)
        layout.addWidget(self.btn_history)
        layout.addWidget(self.btn_settings)
        layout.addStretch()
        return panel

    def _wire_events(self):
        self.btn_dashboard.clicked.connect(lambda: self.navigate(self.PAGE_DASHBOARD))
        self.btn_batch.clicked.connect(lambda: self.navigate(self.PAGE_BATCH))
        self.btn_history.clicked.connect(lambda: self.navigate(self.PAGE_HISTORY))
        self.btn_settings.clicked.connect(lambda: self.navigate(self.PAGE_SETTINGS))

        self.onboarding_page.completed.connect(self._complete_onboarding)
        self.dashboard_page.startBatchRequested.connect(lambda: self.navigate(self.PAGE_BATCH))
        self.dashboard_page.howItWorksRequested.connect(self._show_walkthrough)

        self.batch_page.filesDropped.connect(self._enqueue_files)
        self.batch_page.reviewRequested.connect(self._open_review)
        self.batch_page.cancelRequested.connect(self._cancel_file)

        self.review_page.backRequested.connect(lambda: self.navigate(self.PAGE_BATCH))
        self.review_page.previousRequested.connect(lambda: self._move_review(-1))
        self.review_page.nextRequested.connect(lambda: self._move_review(1))
        self.review_page.applyCurrentRequested.connect(self._apply_current)
        self.review_page.applyAllRequested.connect(self._apply_all)

        self.settings_page.browseRequested.connect(self._choose_default_export_path)
        self.settings_page.openFolderRequested.connect(self._open_default_export_path)
        self.settings_page.settings_saved_signal.connect(self._on_settings_saved)
        self.settings_page.statsResetRequested.connect(self._reset_dashboard_stats)
        self.settings_page.allDataClearedRequested.connect(self._clear_all_app_data)

        self.history_page.deleteSelectedRequested.connect(self._delete_selected_history)
        self.history_page.clearAllRequested.connect(self._clear_all_history)

    def _apply_performance_settings_from_config(self):
        max_threads = int(self.config.get_setting("max_concurrent_files", 2))
        self.threadpool.setMaxThreadCount(max(1, max_threads))

    def _route_initial_page(self):
        if self.config.user_name():
            self.dashboard_page.set_user(self.config.user_name())
            self.navigate(self.PAGE_DASHBOARD)
        else:
            self.stack.setCurrentIndex(self.PAGE_ONBOARDING)
            self._set_nav_checked(None)

    def _complete_onboarding(self, name: str):
        self.config.set_user_name(name)
        self.dashboard_page.set_user(name)
        self.navigate(self.PAGE_DASHBOARD)
        self.toast.show_toast(f"Welcome, {name}")
        self._show_walkthrough()

    def _show_walkthrough(self):
        self.walkthrough_step = 1
        try:
            self.walkthrough_overlay.completed.disconnect()
        except TypeError:
            pass
        self.walkthrough_overlay.completed.connect(self._next_walkthrough_step)
        
        self.navigate(self.PAGE_DASHBOARD)
        QTimer.singleShot(100, self._run_walkthrough_step1)

    def _run_walkthrough_step1(self):
        self.walkthrough_overlay.set_target(
            self.dashboard_page.start_btn, 
            "Step 1: Click 'Start New Batch' to begin.", 
            "Got it"
        )

    def _next_walkthrough_step(self):
        self.walkthrough_overlay.hide()
        if self.walkthrough_step == 1:
            self.walkthrough_step = 2
            self.dashboard_page.startBatchRequested.emit()
            QTimer.singleShot(100, self._run_walkthrough_step2)
        elif self.walkthrough_step == 2:
            self.walkthrough_step = 3
            self.walkthrough_overlay.set_target(
                self.batch_page.dropzone.browse_btn, 
                "Step 3: You can also click here to browse for files.", 
                "Finish"
            )
        else:
            self.walkthrough_step = 0
            
    def _run_walkthrough_step2(self):
        self.walkthrough_overlay.set_target(
            self.batch_page.dropzone, 
            "Step 2: Drag and drop your sensitive documents here.", 
            "Next"
        )

    def navigate(self, page_index: int):
        self.stack.setCurrentIndex(page_index)
        if page_index == self.PAGE_DASHBOARD:
            self._set_nav_checked(self.btn_dashboard)
            self._refresh_dashboard_stats()
        elif page_index == self.PAGE_BATCH:
            self._set_nav_checked(self.btn_batch)
        elif page_index == self.PAGE_HISTORY:
            self._set_nav_checked(self.btn_history)
            self._refresh_history()
        elif page_index == self.PAGE_REVIEW:
            self._set_nav_checked(self.btn_batch)
        elif page_index == self.PAGE_SETTINGS:
            self._set_nav_checked(self.btn_settings)
            self.settings_page.load_from_config(self.config)
        self._update_banner_visibility()

    def _set_nav_checked(self, active_btn: QPushButton | None):
        for btn in (self.btn_dashboard, self.btn_batch, self.btn_history, self.btn_settings):
            btn.setChecked(btn is active_btn)

    def _choose_default_export_path(self):
        start_dir = self.config.default_export_path()
        chosen = QFileDialog.getExistingDirectory(self, "Select Default Export Folder", start_dir)
        if not chosen:
            return
        self.config.set_default_export_path(chosen)
        self.settings_page.set_export_path(chosen)
        self.toast.show_toast("Default save location updated")

    def _on_settings_saved(self, payload: dict):
        if not payload.get("target_entities"):
            self.toast.show_toast("Select at least one target entity")
            return

        export_path = payload.get("default_export_path", "").strip() or self.config.default_export_path()
        payload["default_export_path"] = export_path

        self.config.update_settings(payload)
        self.settings_page.load_from_config(self.config)
        self._apply_performance_settings_from_config()
        self.toast.show_toast("Settings saved")

    def _open_default_export_path(self):
        path = self.config.default_export_path()
        os.makedirs(path, exist_ok=True)
        ok = QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        if not ok:
            self.toast.show_toast("Could not open export folder")

    def _delete_selected_history(self, filenames: list[str]):
        deleted = delete_history_entries(filenames)
        if deleted > 0:
            self.toast.show_toast(f"Deleted {deleted} history entr{'y' if deleted == 1 else 'ies'}")
        self._refresh_history()

    def _clear_all_history(self):
        """Clear entire audit log without touching dashboard stats."""
        clear_all_history()
        self.toast.show_toast("History cleared")
        self._refresh_history()

    def _reset_dashboard_stats(self):
        """Reset only the dashboard counters in config.json (does NOT touch audit log)."""
        self.config.reset_dashboard_counters()
        self.dashboard_page.set_stats(0, 0, 0)
        self.toast.show_toast("Dashboard stats reset")

    def _clear_all_app_data(self):
        """Nuclear option: clear both audit log and dashboard counters."""
        clear_all_history()
        self.config.reset_dashboard_counters()
        self.dashboard_page.set_stats(0, 0, 0)
        self._refresh_history()
        self.toast.show_toast("All app data cleared")

    def _enqueue_files(self, file_paths: list):
        valid = [p for p in file_paths if os.path.isfile(p) and p.lower().endswith((".pdf", ".docx"))]
        if not valid:
            self.toast.show_toast("No supported files detected")
            return

        # Tier Enforcement: Free tier only allows 1 file at a time
        current_tier = self.config.get_setting("license_tier", "Free")
        existing_count = len(self.batch_items)
        if current_tier == "Free" and (len(valid) + existing_count) > 1:
            dialog = LicenseDialog(current_tier, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Update config with new tier and proceed
                self.config.update_settings({
                    "license_key": dialog.license_key,
                    "license_tier": dialog.tier
                })
                self.toast.show_toast(f"Upgraded to {dialog.tier}!")
            else:
                self.toast.show_toast("Free tier is limited to 1 file. Upgrade for batch processing.")
                # Only keep the first file if they didn't upgrade
                valid = valid[:1] if existing_count == 0 else []
                if not valid:
                    return

        # Analytics: track files added (one event per file)
        for path in valid:
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            get_analytics().file_added(file_extension=ext, file_count=len(valid))

        for path in valid:
            file_id = str(uuid.uuid4())
            name = os.path.basename(path)
            action_widget = self.batch_page.add_file_row(file_id, name, path)

            worker = RedactionWorker(
                file_path=path,
                file_id=file_id,
                engine_settings={
                    "confidence_threshold": self.config.get_setting("confidence_threshold", 0.6),
                    "target_entities": self.config.get_setting("target_entities", []),
                    "custom_allow_list": self.config.get_setting("custom_allow_list", []),
                },
            )
            worker.signals.started.connect(self._on_file_started)
            worker.signals.progress.connect(self.update_file_progress)
            worker.signals.finished.connect(self.on_file_ready_for_review)
            worker.signals.error.connect(self.on_file_error)

            self.batch_items[file_id] = {
                "id": file_id,
                "path": path,
                "name": name,
                "worker": worker,
                "status": "Pending",
                "progress": 0,
                "raw_text": "",
                "snippets": [],
                "approved_entities": set(),
                "action_widget": action_widget,
            }
            self.batch_order.append(file_id)
            self.threadpool.start(worker)

        self.toast.show_toast(f"Queued {len(valid)} file(s)")
        self.navigate(self.PAGE_BATCH)
        self._update_banner_visibility()

    def _on_worker_status(self, file_id: str, status: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["status"] = status
        self.batch_page.set_status(file_id, status)
        self._update_banner_visibility()

    def _on_file_started(self, file_id: str):
        self._on_worker_status(file_id, "Analyzing")

    def update_file_progress(self, file_id: str, percentage: int, status_text: str):
        self._on_worker_status(file_id, status_text)
        self._on_worker_progress(file_id, percentage)

    def _on_worker_progress(self, file_id: str, progress: int):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["progress"] = progress
        self.batch_page.set_progress(file_id, progress)
        self._update_banner_visibility()

    def on_file_ready_for_review(self, file_id: str, payload: dict):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["raw_text"] = payload.get("raw_text", "")
        item["snippets"] = payload.get("snippets", [])
        item["approved_entities"] = {s.get("text", "") for s in item["snippets"] if s.get("text", "")}
        item["status"] = "Ready for Review"
        self.batch_page.set_status(file_id, "Ready for Review")
        self.batch_page.set_progress(file_id, 100)
        item["action_widget"].set_review_visible(True)
        item["action_widget"].set_cancel_enabled(False)
        self.toast.show_toast(f"Ready for review: {item['name']}")
        self._update_banner_visibility()

    def on_file_error(self, file_id: str, message: str):
        if message == "Cancelled":
            self._on_worker_cancelled(file_id)
            return
        self._on_worker_failed(file_id, message)

    def _on_worker_failed(self, file_id: str, message: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["status"] = "Failed"
        self.batch_page.set_status(file_id, "Failed")
        item["action_widget"].set_cancel_enabled(False)
        self.toast.show_toast(f"Failed: {item['name']} ({message})")
        self._update_banner_visibility()

    def _on_worker_cancelled(self, file_id: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["status"] = "Cancelled"
        self.batch_page.set_status(file_id, "Cancelled")
        item["action_widget"].set_cancel_enabled(False)
        self.toast.show_toast(f"Cancelled: {item['name']}")
        self._update_banner_visibility()

    def _remove_batch_item(self, file_id: str):
        item = self.batch_items.pop(file_id, None)
        if not item:
            return

        if file_id in self.batch_order:
            self.batch_order.remove(file_id)

        self.batch_page.remove_file_row(file_id)

        redaction_worker = self.redaction_workers.pop(file_id, None)
        if redaction_worker is not None and redaction_worker.isRunning():
            redaction_worker.requestInterruption()

        if self.current_review_id == file_id:
            self.current_review_id = None

        self._sync_review_after_removal()
        self._update_banner_visibility()

    def _sync_review_after_removal(self):
        if self.stack.currentIndex() != self.PAGE_REVIEW:
            return
        reviewable = self._reviewable_ids()
        if not reviewable:
            self.navigate(self.PAGE_BATCH)
            return
        if self.current_review_id not in reviewable:
            self.current_review_id = reviewable[0]
            self._load_review_page(self.current_review_id)

    def _cancel_file(self, file_id: str):
        item = self.batch_items.get(file_id)
        if not item:
            return

        worker = item.get("worker")
        if worker and hasattr(worker, "cancel"):
            worker.cancel()

        self._remove_batch_item(file_id)
        self.toast.show_toast(f"Removed: {item['name']}")

    def _reviewable_ids(self) -> list:
        return [
            fid for fid in self.batch_order
            if self.batch_items.get(fid, {}).get("status") in ("Ready for Review", "Done", "Redacting")
        ]

    def _open_review(self, file_id: str):
        if file_id not in self.batch_items:
            return
        self._persist_review_state()
        self.current_review_id = file_id
        self._load_review_page(file_id)
        # Analytics: review opened — strong engagement signal
        item = self.batch_items.get(file_id, {})
        entity_count = len(item.get("snippets", []))
        get_analytics().review_opened(entity_count=entity_count)
        self.navigate(self.PAGE_REVIEW)

    def _load_review_page(self, file_id: str):
        item = self.batch_items[file_id]
        reviewable = self._reviewable_ids()
        index_1 = reviewable.index(file_id) + 1 if file_id in reviewable else 1
        total = len(reviewable) if reviewable else 1
        self.review_page.set_context(index_1, total, item["name"])
        self.review_page.load_document(item["raw_text"], item["snippets"], item["approved_entities"])

    def _persist_review_state(self):
        if not self.current_review_id:
            return
        item = self.batch_items.get(self.current_review_id)
        if not item:
            return
        item["approved_entities"] = self.review_page.approved_entities()

    def _move_review(self, direction: int):
        reviewable = self._reviewable_ids()
        if not reviewable or self.current_review_id not in reviewable:
            return
        self._persist_review_state()
        idx = reviewable.index(self.current_review_id)
        next_idx = (idx + direction) % len(reviewable)
        self.current_review_id = reviewable[next_idx]
        self._load_review_page(self.current_review_id)

    def _apply_current(self):
        if not self.current_review_id:
            return
        self._persist_review_state()
        self._start_redaction(self.current_review_id)

    def _apply_all(self):
        self._persist_review_state()
        ready = [
            fid for fid in self.batch_order
            if self.batch_items.get(fid, {}).get("status") == "Ready for Review"
        ]
        if not ready:
            self.toast.show_toast("No files ready for batch apply")
            return
        for fid in ready:
            self._start_redaction(fid)

    def _start_redaction(self, file_id: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        if item["status"] in ("Redacting", "Done"):
            return

        export_dir = self.config.default_export_path()
        os.makedirs(export_dir, exist_ok=True)

        original_name = os.path.basename(item["path"])
        stem, ext = os.path.splitext(original_name)
        suffix = self.config.get_setting("file_suffix", "_REDACTED")
        output_path = os.path.join(export_dir, f"{stem}{suffix}{ext}")

        approved_snippets = [
            s for s in item["snippets"] if s.get("text", "") in item["approved_entities"]
        ]

        worker = ApplyRedactionWorker(
            file_id=file_id,
            file_path=item["path"],
            output_path=output_path,
            approved_entities=list(item["approved_entities"]),
            approved_snippets=approved_snippets,
            redaction_style=self.config.get_setting("redaction_style", "[REDACTED]"),
        )
        worker.statusChanged.connect(self._on_worker_status)
        worker.finishedRedaction.connect(self._on_redaction_finished)
        self.redaction_workers[file_id] = worker
        worker.start()

    def _on_redaction_finished(self, file_id: str, output_path: str, success: bool):
        item = self.batch_items.get(file_id)
        if not item:
            return

        if success:
            actions = []
            approved = item["approved_entities"]
            for snippet in item["snippets"]:
                text = snippet.get("text", "")
                if not text:
                    continue
                actions.append(
                    {
                        "entity_text": text,
                        "type": snippet.get("entity_type", "UNKNOWN"),
                        "action": "APPROVED" if text in approved else "REJECTED",
                    }
                )

            reviewer = self.config.user_name() or "UnknownUser"
            self.audit_logger.append_entry(item["name"], reviewer, actions)

            # Analytics: ★ PRIMARY KPI — full workflow completed (Task Completion Rate)
            approved_count = sum(1 for a in actions if a["action"] == "APPROVED")
            rejected_count = sum(1 for a in actions if a["action"] == "REJECTED")
            ext = os.path.splitext(item["name"])[1].lower().lstrip(".")
            get_analytics().export_saved(
                approved_count=approved_count,
                rejected_count=rejected_count,
                file_extension=ext,
            )

            self.toast.show_toast(f"Saved: {item['name']}")
            self._refresh_dashboard_stats()
            self._remove_batch_item(file_id)
        else:
            item["status"] = "Failed"
            self.batch_page.set_status(file_id, "Failed")
            # Analytics: export failed — helps diagnose drop-off
            ext = os.path.splitext(item.get("name", ""))[1].lower().lstrip(".")
            get_analytics().export_failed(file_extension=ext)
            self.toast.show_toast(f"Save failed: {item['name']}")

        if not self.batch_items:
            self.toast.show_toast("Batch complete")

        self._update_banner_visibility()

    def _load_audit_entries(self) -> list:
        log_path = DEFAULT_LOG_FILE
        if not os.path.exists(log_path):
            return []
        with open(log_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _refresh_dashboard_stats(self):
        logs = self._load_audit_entries()
        files_redacted = len(logs)
        approved = 0
        rejected = 0
        for entry in logs:
            for action in entry.get("actions", []):
                if action.get("action") == "APPROVED":
                    approved += 1
                elif action.get("action") == "REJECTED":
                    rejected += 1
        self.dashboard_page.set_stats(files_redacted, approved, rejected)
        if self.config.user_name():
            self.dashboard_page.set_user(self.config.user_name())

    def _refresh_history(self):
        logs = self._load_audit_entries()
        rows = []
        for entry in reversed(logs):
            dt_raw = entry.get("timestamp", "")
            formatted = dt_raw
            try:
                formatted = datetime.datetime.fromisoformat(dt_raw).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

            approved_words = 0
            rejected_items = 0
            for action in entry.get("actions", []):
                text = action.get("entity_text", "")
                if action.get("action") == "APPROVED":
                    approved_words += len(text.split())
                elif action.get("action") == "REJECTED":
                    rejected_items += 1

            rows.append(
                {
                    "file": entry.get("original_filename", "Unknown"),
                    "date": formatted,
                    "words_redacted": approved_words,
                    "rejected_items": rejected_items,
                }
            )
        self.history_page.load_entries(rows)

    def _update_banner_visibility(self):
        active = [
            item for item in self.batch_items.values()
            if item.get("status") in ("Pending", "Analyzing", "Cancelling", "Redacting")
        ]
        on_batch = self.stack.currentIndex() in (self.PAGE_BATCH, self.PAGE_REVIEW)
        if active and not on_batch:
            self.banner.update_text(f"{len(active)} file(s) processing in background")
            self.banner.show()
        else:
            self.banner.hide()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    custom_colors = {
        "[dark]": {
            "primary": "#3B82F6",
            "background": "#0F1117",
            "base": "#1A1D27",
            "border": "#2A2F3D"
        }
    }
    
    custom_css = """
        QMainWindow, QStackedWidget { background-color: #0F1117; }
        #Sidebar { background-color: #13161F; border-right: 1px solid #202432; }
        QFrame { border: none; }
        QPushButton { 
            background-color: #3B82F6; 
            color: white; 
            border-radius: 6px; 
            padding: 8px 16px; 
            font-weight: 600; 
            font-family: 'Inter', 'Segoe UI', sans-serif;
            border: none; 
        }
        QPushButton:hover { background-color: #2563EB; }
        QPushButton:pressed { background-color: #1D4ED8; }
        QListWidget, QTableWidget, QTextEdit { 
            background-color: #151822; 
            border: 1px solid #2A2F3D; 
            color: #E2E8F0; 
            border-radius: 6px;
        }
        QLabel { color: #F8FAFC; font-family: 'Inter', 'Segoe UI', sans-serif; }
        QLineEdit, QComboBox, QSpinBox { 
            background-color: #151822; 
            border: 1px solid #2A2F3D; 
            color: #F8FAFC; 
            border-radius: 6px; 
            padding: 6px 10px; 
        }
    """

    try:
        base_css = qdarktheme.load_stylesheet("dark", custom_colors=custom_colors)
    except TypeError:
        base_css = qdarktheme.load_stylesheet("dark")
        
    app.setStyleSheet(base_css + custom_css)
    app.setFont(QFont("Inter", 10))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
