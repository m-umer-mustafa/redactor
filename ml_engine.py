import logging
import re
from typing import Any, Dict, List

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider

logger = logging.getLogger(__name__)


class MLEngine:
    # Keep defaults strongly aligned with standard Presidio entities.
    DEFAULT_STANDARD_ENTITIES = [
        "PERSON",
        "ORGANIZATION",
        "LOCATION",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "CREDIT_CARD",
        "IBAN_CODE",
    ]

    CUSTOM_ENTITY_NAMES = [
        "CURRENCY_AMOUNT",
        "DATE_DOB",
        "CREDIT_CARD_SPACED",
        "GLOBAL_IBAN",
        "SWIFT_CODE",
        "ROUTING_OR_ACCOUNT_NUMBER",
        "ALPHANUMERIC_ID",
        "PHONE_NUMBER_FALLBACK",
        "ROBUST_ADDRESS_BLOCK",
        "INTERNATIONAL_ADDRESS",
    ]

    # Accept aliases from config and normalize to Presidio entities.
    ENTITY_ALIASES = {
        "PERSON": "PERSON",
        "ORG": "ORGANIZATION",
        "ORGANIZATION": "ORGANIZATION",
        "GPE": "LOCATION",
        "LOC": "LOCATION",
        "LOCATION": "LOCATION",
        "EMAIL": "EMAIL_ADDRESS",
        "EMAIL_ADDRESS": "EMAIL_ADDRESS",
        "PHONE": "PHONE_NUMBER",
        "PHONE_NUMBER": "PHONE_NUMBER",
        "US_SSN": "US_SSN",
        "CREDIT_CARD": "CREDIT_CARD",
        "IBAN": "IBAN_CODE",
        "IBAN_CODE": "IBAN_CODE",
    }

    SAFE_LEGAL_TERMS = [
        "Slack",
        "NDA",
        "Agreement",
        "Transcription",
        "DOB",
        "Patient",
        "Admitted",
        "Hospital",
        "Landlord",
        "Tenant",
        "Premises",
        "Security",
        "Clinical",
        "Email",
        "IBAN",
        "Passport",
        "Number",
        "CONFIDENTIAL",
        "SETTLEMENT",
        "AGREEMENT",
        "ADMISSION",
        "RECORD",
        "INTERNAL",
        "Q3",
        "SSN",
        "Post-Employment Obligations",
    ]

    # Keep PERSON threshold reasonable so names are not dropped.
    ENTITY_MIN_SCORE = {
        "PERSON": 0.55,
    }

    def __init__(
        self,
        use_transformer: bool = False,
        confidence_threshold: float = 0.5,
        target_entities: List[str] | None = None,
        custom_allow_list: List[str] | None = None,
    ):
        self.model_name = "en_core_web_trf" if use_transformer else "en_core_web_lg"
        self.confidence_threshold = float(confidence_threshold)
        self.safe_terms = self.SAFE_LEGAL_TERMS[:] + [
            term.strip() for term in (custom_allow_list or []) if term and term.strip()
        ]
        self.active_entities = self._resolve_active_entities(target_entities)

        logger.info("Initializing ML Engine with local model: %s", self.model_name)

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": self.model_name}],
            "ner_model_configuration": {
                "labels_to_ignore": [],
                "model_to_presidio_entity_mapping": {
                    "PER": "PERSON",
                    "PERSON": "PERSON",
                    "ORG": "ORGANIZATION",
                    "GPE": "LOCATION",
                    "LOC": "LOCATION",
                    "MONEY": "MONEY",
                    "DATE": "DATE_TIME",
                    "TIME": "DATE_TIME",
                },
            },
        }

        provider = NlpEngineProvider(nlp_configuration=configuration)
        self.nlp_engine = provider.create_engine()

        # Explicitly instantiate registry and register recognizers.
        self.registry = RecognizerRegistry()
        self.registry.load_predefined_recognizers(
            nlp_engine=self.nlp_engine,
            languages=["en"],
        )

        self._register_custom_recognizers(self.registry)

        self.analyzer = AnalyzerEngine(
            registry=self.registry,
            nlp_engine=self.nlp_engine,
            supported_languages=["en"],
        )

    def _resolve_active_entities(self, configured_entities: List[str] | None) -> List[str]:
        normalized = []
        for entity in configured_entities or []:
            mapped = self.ENTITY_ALIASES.get(entity.strip().upper()) if entity else None
            if mapped and mapped not in normalized:
                normalized.append(mapped)

        # Critical safety: if empty, use all standard entities.
        if not normalized:
            normalized = self.DEFAULT_STANDARD_ENTITIES[:]

        # Always include custom entities so regex recognizers can fire.
        for custom_name in self.CUSTOM_ENTITY_NAMES:
            if custom_name not in normalized:
                normalized.append(custom_name)

        return normalized

    def _register_custom_recognizers(self, registry: RecognizerRegistry) -> None:
        recognizers = [
            PatternRecognizer(
                supported_entity="PERSON",
                name="person_with_initials_recognizer",
                patterns=[
                    Pattern(
                        name="person_with_initials",
                        regex=r"\b[A-Z][a-z]+\s+[A-Z]\.?\s+[A-Z][a-z]+\b",
                        score=0.95,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="ORGANIZATION",
                name="corporate_suffix_recognizer",
                patterns=[
                    Pattern(
                        name="corporate_suffix",
                        regex=r"\b[A-Z][a-zA-Z\&\-\s,]+\b\s+(?:LLC|Inc\.?|Corp\.?|LLP|GmbH|Ltd\.?)\b",
                        score=0.95,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="ORGANIZATION",
                name="medical_institution_recognizer",
                patterns=[
                    Pattern(
                        name="medical_institution",
                        regex=r"\b[A-Z][a-zA-Z\&\-\s]+\b\s+(?:Hospital|Medical Center|Clinic)\b",
                        score=0.95,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="US_SSN",
                name="ssn_masked_mock_recognizer",
                patterns=[
                    Pattern(
                        name="ssn_masked_mock",
                        regex=r"\b(?:[X\*\d]{3}-[X\*\d]{2}-\d{4})\b",
                        score=0.85,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="CURRENCY_AMOUNT",
                name="currency_amount_recognizer",
                patterns=[
                    Pattern(
                        name="currency_amount",
                        regex=r"[\$\€\£]\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                        score=0.8,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="DATE_DOB",
                name="date_dob_recognizer",
                patterns=[
                    Pattern(
                        name="date_dob",
                        regex=r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
                        score=0.6,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="CREDIT_CARD_SPACED",
                name="spaced_credit_card_recognizer",
                patterns=[
                    Pattern(
                        name="spaced_credit_card",
                        regex=r"\b(?:\d{4}[ -]){3}\d{4}\b",
                        score=0.85,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="GLOBAL_IBAN",
                name="global_iban_recognizer",
                patterns=[
                    Pattern(
                        name="global_iban",
                        regex=r"\b[a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{11,28}\b",
                        score=0.85,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="SWIFT_CODE",
                name="swift_bic_recognizer",
                patterns=[
                    Pattern(
                        name="swift_bic",
                        regex=r"\b[a-zA-Z]{6}[a-zA-Z0-9]{2}(?:[a-zA-Z0-9]{3})?\b",
                        score=0.01,
                    )
                ],
                context=["swift", "bic"],
            ),
            PatternRecognizer(
                supported_entity="ROUTING_OR_ACCOUNT_NUMBER",
                name="routing_account_number_recognizer",
                patterns=[
                    Pattern(
                        name="routing_account_digits",
                        regex=r"\b\d{8,12}\b",
                        score=0.8,
                    )
                ],
                context=["routing", "account", "deposit", "wire"],
            ),
            PatternRecognizer(
                supported_entity="ALPHANUMERIC_ID",
                name="alphanumeric_id_recognizer",
                patterns=[
                    Pattern(
                        name="alphanumeric_id",
                        regex=r"\b(?=[A-Za-z0-9\-]{7,10}\b)(?:[A-Za-z]+[\-]*\d+|\d+[\-]*[A-Za-z]+)[A-Za-z0-9\-]*\b",
                        score=0.8,
                    )
                ],
                context=["id", "passport", "employee", "number"],
            ),
            PatternRecognizer(
                supported_entity="PHONE_NUMBER_FALLBACK",
                name="phone_fallback_recognizer",
                patterns=[
                    Pattern(
                        name="phone_fallback",
                        regex=r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
                        score=0.6,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="ROBUST_ADDRESS_BLOCK",
                name="robust_address_block_recognizer",
                patterns=[
                    Pattern(
                        name="robust_address",
                        regex=r"\b\d{1,5}\s+(?:[A-Za-z0-9\#]+\s+){1,5}(?:Street|St|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Ct|Court|Cir|Circle|Way|Terrace|Ter|Apt|Suite)[a-zA-Z0-9\s,&#\.\-]+?\b[A-Z]{2,15}\b\s+\d{5}(?:-\d{4})?\b",
                        score=0.75,
                    )
                ],
            ),
            PatternRecognizer(
                supported_entity="INTERNATIONAL_ADDRESS",
                name="european_address_recognizer",
                patterns=[
                    Pattern(
                        name="european_address",
                        regex=r"\b[A-Z][a-zA-Z\s\-ßäöü]+\s\d{1,4},\s?\d{4,5}\s+[A-Z][a-zA-Z\s\-ßäöü]+\b",
                        score=0.85,
                    )
                ],
            ),
        ]

        for recognizer in recognizers:
            registry.add_recognizer(recognizer)

    def _is_allow_list_match(self, entity_text: str) -> bool:
        """Check if entity text matches allow-list (case-insensitive exact match)."""
        normalized = entity_text.strip().lower()
        if not normalized:
            return False
        for safe_term in self.safe_terms:
            safe = safe_term.lower()
            # Exact match (case-insensitive) or substring match for safety
            if normalized == safe or normalized in safe or safe in normalized:
                return True
        return False

    def _passes_entity_threshold(self, result: RecognizerResult) -> bool:
        min_score = self.ENTITY_MIN_SCORE.get(result.entity_type, self.confidence_threshold)
        return result.score >= min_score

    @staticmethod
    def _is_fragmented_person_name(entity_text: str) -> bool:
        # Keep single-token person names if they look like title-case words,
        # but filter very short/noisy tokens.
        tokens = [t for t in re.split(r"\s+", entity_text.strip()) if t]
        if len(tokens) >= 2:
            return False
        if not tokens:
            return True
        token = tokens[0]
        return len(token) < 3

    def _apply_allow_list_postprocessing(self, results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
        """
        Post-process results to explicitly filter against allow-list with case-insensitive matching.
        This ensures boilerplate terms are removed even if spaCy flagged them.
        """
        filtered = []
        for result in results:
            entity_text = text[result.start:result.end]
            
            # Check if entity matches allow-list (case-insensitive)
            normalized = entity_text.strip().lower()
            is_allowed = False
            
            for safe_term in self.safe_terms:
                safe_lower = safe_term.lower()
                # Exact match preferred, but also check substring matches
                if normalized == safe_lower or normalized in safe_lower or safe_lower in normalized:
                    is_allowed = True
                    break
            
            if not is_allowed:
                filtered.append(result)
        
        return filtered

    def analyze_text(self, text: str) -> List[RecognizerResult]:
        if not text.strip():
            return []

        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.active_entities,
            score_threshold=self.confidence_threshold,
            allow_list=self.safe_terms,
        )

        # First pass: threshold check and fragmentation filtering
        filtered = []
        for result in results:
            entity_text = text[result.start:result.end]

            if not self._passes_entity_threshold(result):
                continue
            if result.entity_type == "PERSON" and self._is_fragmented_person_name(entity_text):
                continue

            filtered.append(result)

        # Second pass: explicit allow-list post-processing (case-insensitive)
        filtered = self._apply_allow_list_postprocessing(filtered, text)

        filtered.sort(key=lambda x: x.start)
        return filtered

    def get_candidate_snippets(
        self,
        text: str,
        results: List[RecognizerResult],
        context_chars: int = 30,
    ) -> List[Dict[str, Any]]:
        snippets = []
        for res in results:
            start_idx = max(0, res.start - context_chars)
            end_idx = min(len(text), res.end + context_chars)

            snippet_text = text[start_idx:end_idx]
            entity_text = text[res.start:res.end]

            snippets.append(
                {
                    "entity_type": res.entity_type,
                    "score": res.score,
                    "text": entity_text,
                    "start": res.start,
                    "end": res.end,
                    "context_snippet": f"...{snippet_text}...",
                }
            )

        return snippets
