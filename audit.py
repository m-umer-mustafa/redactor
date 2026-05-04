import json
import os
import sys
import datetime
from typing import List, Dict, Any


def get_audit_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "Redactor", "audit_data")

DEFAULT_LOG_DIR = get_audit_dir()
DEFAULT_LOG_FILE = os.path.join(DEFAULT_LOG_DIR, "redaction_audit_log.json")


def _ensure_log_file(log_file: str = DEFAULT_LOG_FILE) -> None:
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump([], f)


def _read_log_entries(log_file: str = DEFAULT_LOG_FILE) -> List[Dict[str, Any]]:
    _ensure_log_file(log_file)
    with open(log_file, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


def _write_log_entries(entries: List[Dict[str, Any]], log_file: str = DEFAULT_LOG_FILE) -> None:
    _ensure_log_file(log_file)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=4)


def delete_history_entries(filenames: List[str], log_file: str = DEFAULT_LOG_FILE) -> int:
    """
    Remove all audit entries whose original_filename is in filenames.
    Returns number of deleted entries.
    """
    if not filenames:
        return 0

    target = set(filenames)
    entries = _read_log_entries(log_file)
    kept = [entry for entry in entries if entry.get("original_filename") not in target]
    deleted_count = len(entries) - len(kept)
    _write_log_entries(kept, log_file)
    return deleted_count


def clear_all_history(log_file: str = DEFAULT_LOG_FILE) -> None:
    """Overwrite audit history file with an empty list."""
    _write_log_entries([], log_file)


class AuditLogger:
    """
    Maintains a local JSON audit log required for legal compliance.
    Records every detected PII entity and whether a human approved or rejected it.
    """

    def __init__(self, log_dir: str = None):
        self.log_dir = log_dir or DEFAULT_LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "redaction_audit_log.json")

    def append_entry(self, filename: str, reviewer: str, entities: List[Dict[str, Any]]):
        """Append an action log for a given file to the permanent audit record."""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "original_filename": filename,
            "reviewer_id": reviewer,
            "actions": entities
            # Format ex: [{"entity_text": "John Doe", "type": "PERSON", "action": "APPROVED"}, ...]
        }

        logs = _read_log_entries(self.log_file)
        logs.append(entry)
        _write_log_entries(logs, self.log_file)

    def delete_history_entries(self, filenames: List[str]) -> int:
        return delete_history_entries(filenames, self.log_file)

    def clear_all_history(self) -> None:
        clear_all_history(self.log_file)
