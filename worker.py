import os
from PyQt6.QtCore import QThread, pyqtSignal
from ml_engine import MLEngine
from document_parsers import DocumentParser

class MLWorker(QThread):
    """
    Runs the ML inference in a separate thread to keep the PyQt6 GUI responsive.
    """
    finished = pyqtSignal(str, list, str) # text, results_list, original_filename
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit("Loading completely offline AI Models...")
            from ml_engine import MLEngine
            ml_engine = MLEngine()
            
            self.progress.emit("Extracting text from document...")
            text = DocumentParser.parse(self.file_path)
            
            if not text:
                self.error.emit("Could not extract any text from the document.")
                return
                
            self.progress.emit("Running rigorous PII analysis. This may take a minute...")
            results = ml_engine.analyze_text(text)
            
            # Extract snippets for the UI
            snippets = ml_engine.get_candidate_snippets(text, results)
            
            filename = os.path.basename(self.file_path)
            self.finished.emit(text, snippets, filename)
            
        except Exception as e:
            self.error.emit(str(e))
