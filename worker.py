import os
import threading

from PyQt6.QtCore import QObject, QRunnable, QThread, pyqtSignal, pyqtSlot

from document_parsers import DocumentParser
from ml_engine import MLEngine
from redactor import Redactor


class WorkerSignals(QObject):
    """
    Signal container for QRunnable workers.
    """

    started = pyqtSignal(str)  # file_id
    progress = pyqtSignal(str, int, str)  # file_id, percent, status text
    finished = pyqtSignal(str, dict)  # file_id, payload
    error = pyqtSignal(str, str)  # file_id, error message


class SharedAnalyzerManager:
    """
    Lazily initializes and shares a single MLEngine instance across workers.
    The analysis call is protected so the shared analyzer isn't accessed
    concurrently in a non-thread-safe way.
    """

    _init_lock = threading.Lock()
    _analyze_lock = threading.Lock()
    _engine = None
    _engine_key = None

    @staticmethod
    def _key_from_settings(settings: dict | None, use_transformer: bool) -> tuple:
        cfg = settings or {}
        entities = tuple(sorted(cfg.get("target_entities", [])))
        allow = tuple(sorted(cfg.get("custom_allow_list", [])))
        threshold = float(cfg.get("confidence_threshold", 0.6))
        return (use_transformer, threshold, entities, allow)

    @classmethod
    def get_engine(cls, use_transformer: bool = False, settings: dict | None = None) -> MLEngine:
        key = cls._key_from_settings(settings, use_transformer)
        if cls._engine is None or cls._engine_key != key:
            with cls._init_lock:
                if cls._engine is None or cls._engine_key != key:
                    cfg = settings or {}
                    cls._engine = MLEngine(
                        use_transformer=use_transformer,
                        confidence_threshold=float(cfg.get("confidence_threshold", 0.6)),
                        target_entities=cfg.get("target_entities") or None,
                        custom_allow_list=cfg.get("custom_allow_list") or None,
                    )
                    cls._engine_key = key
        return cls._engine

    @classmethod
    def analyze(cls, text: str, use_transformer: bool = False, settings: dict | None = None):
        engine = cls.get_engine(use_transformer=use_transformer, settings=settings)
        with cls._analyze_lock:
            results = engine.analyze_text(text)
            snippets = engine.get_candidate_snippets(text, results)
        return results, snippets


class RedactionWorker(QRunnable):
    """
    QRunnable worker for extraction + PII analysis in QThreadPool.
    """

    def __init__(
        self,
        file_path: str,
        file_id: str,
        analyzer_engine: MLEngine | None = None,
        use_transformer: bool = False,
        engine_settings: dict | None = None,
    ):
        super().__init__()
        self.file_path = file_path
        self.file_id = file_id
        self.analyzer_engine = analyzer_engine
        self.use_transformer = use_transformer
        self.engine_settings = engine_settings or {}
        self.signals = WorkerSignals()
        self._cancel_requested = threading.Event()

    def cancel(self):
        self._cancel_requested.set()

    def _is_cancelled(self) -> bool:
        return self._cancel_requested.is_set()

    @pyqtSlot()
    def run(self):
        try:
            if self._is_cancelled():
                self.signals.error.emit(self.file_id, "Cancelled")
                return

            self.signals.started.emit(self.file_id)
            self.signals.progress.emit(self.file_id, 20, "Extracted Text")

            raw_text = DocumentParser.parse(self.file_path)
            if not raw_text:
                self.signals.error.emit(self.file_id, "Could not extract text from file")
                return

            if self._is_cancelled():
                self.signals.error.emit(self.file_id, "Cancelled")
                return

            self.signals.progress.emit(self.file_id, 60, "Analyzing Entities")

            if self.analyzer_engine is not None:
                results = self.analyzer_engine.analyze_text(raw_text)
                snippets = self.analyzer_engine.get_candidate_snippets(raw_text, results)
            else:
                results, snippets = SharedAnalyzerManager.analyze(
                    raw_text,
                    use_transformer=self.use_transformer,
                    settings=self.engine_settings,
                )

            if self._is_cancelled():
                self.signals.error.emit(self.file_id, "Cancelled")
                return

            payload = {
                "file_id": self.file_id,
                "file_path": self.file_path,
                "filename": os.path.basename(self.file_path),
                "raw_text": raw_text,
                "snippets": snippets,
            }
            self.signals.progress.emit(self.file_id, 100, "Ready for Review")
            self.signals.finished.emit(self.file_id, payload)
        except Exception as exc:
            self.signals.error.emit(self.file_id, str(exc))


class ApplyRedactionWorker(QThread):
    """
    Background file-save redaction worker to avoid blocking the UI.
    """

    statusChanged = pyqtSignal(str, str)  # file_id, status
    finishedRedaction = pyqtSignal(str, str, bool)  # file_id, output_path, success

    def __init__(
        self,
        file_id: str,
        file_path: str,
        output_path: str,
        approved_entities: list[str],
        approved_snippets: list[dict] | None = None,
        redaction_style: str = "[REDACTED]",
    ):
        super().__init__()
        self.file_id = file_id
        self.file_path = file_path
        self.output_path = output_path
        self.approved_entities = approved_entities
        self.approved_snippets = approved_snippets or []
        self.redaction_style = redaction_style

    def run(self):
        self.statusChanged.emit(self.file_id, "Redacting")
        ok = Redactor.redact(
            self.file_path,
            self.output_path,
            self.approved_entities,
            approved_snippets=self.approved_snippets,
            redaction_style=self.redaction_style,
        )
        self.finishedRedaction.emit(self.file_id, self.output_path, ok)


def build_default_output_path(file_path: str) -> str:
    base, ext = os.path.splitext(file_path)
    return f"{base}_REDACTED{ext}"
