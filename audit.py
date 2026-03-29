import json
import os
import datetime
from typing import List, Dict, Any

class AuditLogger:
    """
    Maintains a local JSON audit log required for legal compliance.
    Records every detected PII entity and whether a human approved or rejected it.
    """
    
    def __init__(self, log_dir: str = "audit_data"):
        self.log_dir = log_dir
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
        
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
                    
        logs.append(entry)
        
        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=4)
