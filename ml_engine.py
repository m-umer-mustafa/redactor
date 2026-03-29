import logging
from typing import List, Dict, Any
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer import PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider

logger = logging.getLogger(__name__)

class MLEngine:
    DEFAULT_TARGET_ENTITIES = [
        "PERSON",
        "LOCATION",
        "ORGANIZATION",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "MASKED_US_SSN",
        "IBAN_CODE",
        "CREDIT_CARD",
        "ACCOUNT_ENDING",
        "CURRENCY_AMOUNT",
        "MONEY",
        "FACILITY",
        "PRODUCT",
        "STREET_ADDRESS",
        "US_ZIP_CODE",
    ]

    SAFE_LEGAL_TERMS = [
        "Confidential Settlement and Release Agreement",
        "Post-Employment Obligations",
        "Operations",
        "SSN",
        "Employer",
        "Employee",
    ]

    # Apply stricter thresholds to noisy general NER classes often over-triggered
    # by legal title-cased boilerplate text.
    ENTITY_MIN_SCORE = {
        "ORGANIZATION": 0.85,
        "PERSON": 0.85,
        "FACILITY": 0.85,
        "PRODUCT": 0.85,
    }

    def __init__(
        self,
        use_transformer: bool = False,
        confidence_threshold: float = 0.6,
        target_entities: List[str] | None = None,
        custom_allow_list: List[str] | None = None,
    ):
        """
        Initializes the fully local NLP engine for PII detection.
        We default to the Large model (en_core_web_lg) for high accuracy and speed 
        without PyTorch DLL dependencies on Windows.
        """
        self.model_name = "en_core_web_trf" if use_transformer else "en_core_web_lg"
        self.confidence_threshold = float(confidence_threshold)
        self.target_entities = target_entities[:] if target_entities else self.DEFAULT_TARGET_ENTITIES[:]
        self.safe_terms = self.SAFE_LEGAL_TERMS[:] + [
            term.strip() for term in (custom_allow_list or []) if term and term.strip()
        ]
        
        logger.info(f"Initializing ML Engine with local model: {self.model_name}")
        
        try:
            # We configure the NLP engine to use the downloaded model
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": self.model_name}],
                # Route additional spaCy labels so Presidio can return them as entities.
                # This helps expose MONEY/FAC/PRODUCT when present in model output.
                "ner_model_configuration": {
                    "labels_to_ignore": [],
                    "model_to_presidio_entity_mapping": {
                        "PER": "PERSON",
                        "PERSON": "PERSON",
                        "LOC": "LOCATION",
                        "GPE": "LOCATION",
                        "ORG": "ORGANIZATION",
                        "DATE": "DATE_TIME",
                        "TIME": "DATE_TIME",
                        "MONEY": "MONEY",
                        "FAC": "FACILITY",
                        "PRODUCT": "PRODUCT"
                    }
                }
            }
            
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            
            # The AnalyzerEngine runs the text against the model + robust RegEx rules
            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine, 
                supported_languages=["en"]
            )

            self._register_custom_recognizers()
            logger.info("ML Engine initialized successfully.")
        except OSError as e:
            logger.error(f"Failed to load model {self.model_name}. Ensure you ran: python -m spacy download {self.model_name}")
            raise e

    def _register_custom_recognizers(self) -> None:
        """
        Register regex recognizers for legal-document leakage cases that default
        recognizers often miss (masked SSNs, account endings, currency amounts,
        and fragmented address pieces).
        """
        custom_recognizers = [
            PatternRecognizer(
                supported_entity="MASKED_US_SSN",
                name="masked_us_ssn_recognizer",
                patterns=[
                    Pattern(
                        name="masked_ssn",
                        regex=r"\b(?:\*|X|x){3}-(?:\*|X|x){2}-\d{4}\b",
                        score=0.8,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="CURRENCY_AMOUNT",
                name="currency_amount_recognizer",
                patterns=[
                    Pattern(
                        name="currency_dollar_amount",
                        regex=r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                        score=0.8,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="ACCOUNT_ENDING",
                name="account_ending_recognizer",
                patterns=[
                    Pattern(
                        name="account_or_card_ending",
                        regex=r"\b(?:ending in|account|card)\s+\d{4}\b",
                        score=0.8,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="STREET_ADDRESS",
                name="street_address_recognizer",
                patterns=[
                    Pattern(
                        name="basic_us_street_address",
                        regex=r"\b\d+\s+[A-Za-z0-9\s\.\-]+?(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Terrace|Ter|Way)\b",
                        score=0.6,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="US_ZIP_CODE",
                name="us_zip_code_recognizer",
                patterns=[
                    Pattern(
                        name="us_zip_code",
                        regex=r"\b\d{5}(?:-\d{4})?\b",
                        score=0.6,
                    ),
                ],
            ),
        ]

        for recognizer in custom_recognizers:
            self.analyzer.registry.add_recognizer(recognizer)

    def _is_allow_list_match(self, entity_text: str) -> bool:
        """
        Ignore exact and partial matches for safe legal boilerplate terms.
        """
        normalized = entity_text.strip().lower()
        if not normalized:
            return False

        for safe_term in self.safe_terms:
            safe = safe_term.lower()
            if normalized == safe:
                return True
            if normalized in safe or safe in normalized:
                return True
        return False

    @classmethod
    def _passes_entity_threshold(cls, result: RecognizerResult) -> bool:
        min_score = cls.ENTITY_MIN_SCORE.get(result.entity_type, 0.6)
        return result.score >= min_score

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
            entities=self.target_entities,
            score_threshold=self.confidence_threshold,
        )

        filtered_results = []
        for result in results:
            entity_text = text[result.start:result.end]

            if self._is_allow_list_match(entity_text):
                continue

            if not self._passes_entity_threshold(result):
                continue

            filtered_results.append(result)
        
        # Sort by start position for easier handling
        filtered_results.sort(key=lambda x: x.start)
        return filtered_results

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
