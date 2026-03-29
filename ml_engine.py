import logging
from typing import List, Dict, Any
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

logger = logging.getLogger(__name__)

class MLEngine:
    def __init__(self, use_transformer: bool = False):
        """
        Initializes the fully local NLP engine for PII detection.
        We default to the Large model (en_core_web_lg) for high accuracy and speed 
        without PyTorch DLL dependencies on Windows.
        """
        self.model_name = "en_core_web_trf" if use_transformer else "en_core_web_lg"
        
        logger.info(f"Initializing ML Engine with local model: {self.model_name}")
        
        try:
            # We configure the NLP engine to use the downloaded model
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": self.model_name}]
            }
            
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            
            # The AnalyzerEngine runs the text against the model + robust RegEx rules
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine, 
                supported_languages=["en"]
            )
            logger.info("ML Engine initialized successfully.")
        except OSError as e:
            logger.error(f"Failed to load model {self.model_name}. Ensure you ran: python -m spacy download {self.model_name}")
            raise e

    def analyze_text(self, text: str) -> List[RecognizerResult]:
        """
        Analyzes a block of text and returns a list of PII candidate results.
        Runs completely offline.
        """
        if not text.strip():
            return []
            
        # We target specific legal/sensitive entities for the MVP
        # such as Person names, Organizations, Locations, Emails, Phone numbers
        results = self.analyzer.analyze(
            text=text,
            language='en',
            entities=["PERSON", "LOCATION", "ORGANIZATION", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "IBAN_CODE", "CREDIT_CARD"],
            score_threshold=0.6 # Minimum confidence
        )
        
        # Sort by start position for easier handling
        results.sort(key=lambda x: x.start)
        return results

    def get_candidate_snippets(self, text: str, results: List[RecognizerResult], context_chars: int = 30) -> List[Dict[str, Any]]:
        """
        Helper method to extract the text snippet around the detected PII for the Review UI.
        """
        snippets = []
        for res in results:
            start_idx = max(0, res.start - context_chars)
            end_idx = min(len(text), res.end + context_chars)
            
            snippet_text = text[start_idx:end_idx]
            entity_text = text[res.start:res.end]
            
            snippets.append({
                "entity_type": res.entity_type,
                "score": res.score,
                "text": entity_text,
                "start": res.start,
                "end": res.end,
                "context_snippet": f"...{snippet_text}..."
            })
            
        return snippets
