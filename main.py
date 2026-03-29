import datetime
import json
import os
import sys
import uuid
import multiprocessing

import qdarktheme
from PyQt6.QtCore import Qt, pyqtSignal, QThreadPool
from PyQt6.QtGui import QFont, QIcon, QGuiApplication, QColor, QTextCursor, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from audit import AuditLogger
from ui_components import (
    BackgroundProgressBanner,
    MultiFileDropZone,
    RowActionWidget,
    ToastNotification,
)
from worker import RedactionWorker, ApplyRedactionWorker, build_default_output_path


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
    def __init__(self, path: str = "config.json"):
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


class SidebarButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                text-align: left;
                padding: 10px 12px;
                border-radius: 8px;
                color: #d4d4d8;
            }
            QPushButton:checked {
                background-color: #25314f;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton:hover:!checked {
                background-color: #1f293e;
            }
            """
        )


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
            panel.setStyleSheet("background:#1d1f25; border:1px solid #31353f; border-radius:10px;")
            p_layout = QVBoxLayout(panel)
            p_layout.addWidget(widget)
            stats_row.addWidget(panel)

        self.start_btn = QPushButton("Start New Batch")
        self.start_btn.clicked.connect(self.startBatchRequested.emit)

        layout.addWidget(self.greeting)
        layout.addLayout(stats_row)
        layout.addWidget(self.start_btn)
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
        self.dropzone.setMinimumHeight(140)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Filename", "Status", "Progress", "Actions", "Path"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(4, True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.dropzone)
        layout.addWidget(self.table)

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
        return row, action_widget

    def set_status(self, row: int, value: str):
        self.table.item(row, 1).setText(value)

    def set_progress(self, row: int, value: int):
        self.table.item(row, 2).setText(f"{value}%")


class HistoryPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by file name...")
        self.search_input.textChanged.connect(self._filter_rows)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Date", "Words Redacted", "Rejected Items"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(self.search_input)
        layout.addWidget(self.table)

    def load_entries(self, entries: list):
        self.table.setRowCount(0)
        for row_data in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(row_data["file"]))
            self.table.setItem(row, 1, QTableWidgetItem(row_data["date"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(row_data["words_redacted"])))
            self.table.setItem(row, 3, QTableWidgetItem(str(row_data["rejected_items"])))
        self._filter_rows(self.search_input.text())

    def _filter_rows(self, query: str):
        term = query.strip().lower()
        for row in range(self.table.rowCount()):
            file_item = self.table.item(row, 0)
            file_name = file_item.text().lower() if file_item else ""
            hide = bool(term) and term not in file_name
            self.table.setRowHidden(row, hide)


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

        body = QHBoxLayout()
        self.text_browser = QTextBrowser()
        self.entity_list = QListWidget()
        self.entity_list.itemChanged.connect(self._on_item_changed)
        self.entity_list.setMaximumWidth(420)

        body.addWidget(self.text_browser)
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
        root.addLayout(body)
        root.addLayout(actions)

    def set_context(self, index_1_based: int, total: int, file_name: str):
        self.context_label.setText(f"File {index_1_based} of {total}  |  {file_name}")

    def load_document(self, raw_text: str, snippets: list, approved_entities: set):
        self._approved = set(approved_entities)
        self._snippets = list(snippets)
        self.text_browser.setPlainText(raw_text)
        self.entity_list.blockSignals(True)
        self.entity_list.clear()

        seen = set()
        for snippet in snippets:
            txt = snippet.get("text", "")
            if not txt or txt in seen:
                continue
            seen.add(txt)

            item = QListWidgetItem(f"{txt}  [{snippet.get('entity_type', 'UNKNOWN')}]")
            item.setData(Qt.ItemDataRole.UserRole, txt)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if txt in self._approved else Qt.CheckState.Unchecked)
            self.entity_list.addItem(item)

        self.entity_list.blockSignals(False)
        self._apply_highlighting()

    def _on_item_changed(self, item: QListWidgetItem):
        entity = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._approved.add(entity)
        else:
            self._approved.discard(entity)
        self._apply_highlighting()

    def _apply_highlighting(self):
        doc = self.text_browser.document()
        if doc is None:
            return

        approved_format = QTextCharFormat()
        approved_format.setBackground(QColor("#f8c8d4"))  # Light pink/red

        rejected_format = QTextCharFormat()
        rejected_format.setBackground(QColor("#cdeccf"))  # Light green

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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("The Redactor")
        self.setMinimumSize(800, 600)

        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_responsive_window_geometry()

        self.config = AppConfig()
        self.audit_logger = AuditLogger()

        self.batch_items = {}
        self.batch_order = []
        self.current_review_id = None
        self.redaction_workers = {}
        self.threadpool = QThreadPool()
        # Keep this low because en_core_web_lg + Presidio are memory-heavy.
        self.threadpool.setMaxThreadCount(2)

        self.toast = ToastNotification(self)

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

        self.stack.addWidget(self.onboarding_page)
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.batch_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.review_page)

        self._wire_events()
        self._route_initial_page()
        self._refresh_dashboard_stats()

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
        panel.setFixedWidth(230)
        panel.setStyleSheet("background-color: #15171d; border-right: 1px solid #262a35;")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 22, 16, 16)
        layout.setSpacing(8)

        brand = QLabel("THE REDACTOR")
        brand.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        brand.setStyleSheet("color: #f4f4f5;")

        self.btn_dashboard = SidebarButton("Dashboard")
        self.btn_batch = SidebarButton("Batch Redaction")
        self.btn_history = SidebarButton("History")

        layout.addWidget(brand)
        layout.addSpacing(18)
        layout.addWidget(self.btn_dashboard)
        layout.addWidget(self.btn_batch)
        layout.addWidget(self.btn_history)
        layout.addStretch()
        return panel

    def _wire_events(self):
        self.btn_dashboard.clicked.connect(lambda: self.navigate(self.PAGE_DASHBOARD))
        self.btn_batch.clicked.connect(lambda: self.navigate(self.PAGE_BATCH))
        self.btn_history.clicked.connect(lambda: self.navigate(self.PAGE_HISTORY))

        self.onboarding_page.completed.connect(self._complete_onboarding)
        self.dashboard_page.startBatchRequested.connect(lambda: self.navigate(self.PAGE_BATCH))

        self.batch_page.filesDropped.connect(self._enqueue_files)
        self.batch_page.reviewRequested.connect(self._open_review)
        self.batch_page.cancelRequested.connect(self._cancel_file)

        self.review_page.backRequested.connect(lambda: self.navigate(self.PAGE_BATCH))
        self.review_page.previousRequested.connect(lambda: self._move_review(-1))
        self.review_page.nextRequested.connect(lambda: self._move_review(1))
        self.review_page.applyCurrentRequested.connect(self._apply_current)
        self.review_page.applyAllRequested.connect(self._apply_all)

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
        self._update_banner_visibility()

    def _set_nav_checked(self, active_btn: QPushButton | None):
        for btn in (self.btn_dashboard, self.btn_batch, self.btn_history):
            btn.setChecked(btn is active_btn)

    def _enqueue_files(self, file_paths: list):
        valid = [p for p in file_paths if os.path.isfile(p) and p.lower().endswith((".pdf", ".docx"))]
        if not valid:
            self.toast.show_toast("No supported files detected")
            return

        for path in valid:
            file_id = str(uuid.uuid4())
            name = os.path.basename(path)
            row, action_widget = self.batch_page.add_file_row(file_id, name, path)

            worker = RedactionWorker(file_path=path, file_id=file_id)
            worker.signals.started.connect(self._on_file_started)
            worker.signals.progress.connect(self.update_file_progress)
            worker.signals.finished.connect(self.on_file_ready_for_review)
            worker.signals.error.connect(self.on_file_error)

            self.batch_items[file_id] = {
                "id": file_id,
                "path": path,
                "name": name,
                "row": row,
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
        self.batch_page.set_status(item["row"], status)
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
        self.batch_page.set_progress(item["row"], progress)
        self._update_banner_visibility()

    def on_file_ready_for_review(self, file_id: str, payload: dict):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["raw_text"] = payload.get("raw_text", "")
        item["snippets"] = payload.get("snippets", [])
        item["approved_entities"] = {s.get("text", "") for s in item["snippets"] if s.get("text", "")}
        item["status"] = "Ready for Review"
        self.batch_page.set_status(item["row"], "Ready for Review")
        self.batch_page.set_progress(item["row"], 100)
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
        self.batch_page.set_status(item["row"], "Failed")
        item["action_widget"].set_cancel_enabled(False)
        self.toast.show_toast(f"Failed: {item['name']} ({message})")
        self._update_banner_visibility()

    def _on_worker_cancelled(self, file_id: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        item["status"] = "Cancelled"
        self.batch_page.set_status(item["row"], "Cancelled")
        item["action_widget"].set_cancel_enabled(False)
        self.toast.show_toast(f"Cancelled: {item['name']}")
        self._update_banner_visibility()

    def _cancel_file(self, file_id: str):
        item = self.batch_items.get(file_id)
        if not item:
            return
        worker = item.get("worker")
        if worker and hasattr(worker, "cancel"):
            item["status"] = "Cancelling"
            self.batch_page.set_status(item["row"], "Cancelling")
            worker.cancel()

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

        output_path = build_default_output_path(item["path"])
        worker = ApplyRedactionWorker(
            file_id=file_id,
            file_path=item["path"],
            output_path=output_path,
            approved_entities=list(item["approved_entities"]),
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
            item["status"] = "Done"
            self.batch_page.set_status(item["row"], "Done")
            self.batch_page.set_progress(item["row"], 100)
            item["action_widget"].set_cancel_enabled(False)

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
            self.toast.show_toast(f"Saved: {item['name']}")
            self._refresh_dashboard_stats()
        else:
            item["status"] = "Failed"
            self.batch_page.set_status(item["row"], "Failed")
            self.toast.show_toast(f"Save failed: {item['name']}")

        if all(self.batch_items[fid]["status"] == "Done" for fid in self._reviewable_ids()):
            self.toast.show_toast("Batch complete")

        self._update_banner_visibility()

    def _load_audit_entries(self) -> list:
        log_path = os.path.join("audit_data", "redaction_audit_log.json")
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
    app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    app.setFont(QFont("Inter", 10))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
