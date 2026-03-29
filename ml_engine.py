import logging
from typing import List, Dict, Any
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer import PatternRecognizer, Pattern
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
                        name="masked_us_ssn_x",
                        # Matches XXX-XX-1234 and xxx-xx-1234
                        regex=r"\b[xX]{3}-[xX]{2}-\d{4}\b",
                        score=0.95,
                    ),
                    Pattern(
                        name="masked_us_ssn_star",
                        # Matches ***-**-1234
                        regex=r"\b\*{3}-\*{2}-\d{4}\b",
                        score=0.95,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="ACCOUNT_ENDING",
                name="account_ending_recognizer",
                patterns=[
                    Pattern(
                        name="ending_in_4_digits",
                        # Matches: ending in 8391, card ending in 4092
                        regex=r"\b(?:account|acct|card|checking\s+account|savings\s+account|credit\s+card|debit\s+card|amex|visa|mastercard)?(?:\s+\w+){0,6}\s+ending\s+(?:in|with)\s+\d{4}\b",
                        score=0.85,
                    ),
                    Pattern(
                        name="simple_ending_in_4_digits",
                        regex=r"\bending\s+(?:in|with)\s+\d{4}\b",
                        score=0.8,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="CURRENCY_AMOUNT",
                name="currency_amount_recognizer",
                patterns=[
                    Pattern(
                        name="usd_amount",
                        # Matches: $85,000.00, $1,250, $99.99
                        regex=r"(?<!\w)\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b",
                        score=0.85,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="STREET_ADDRESS",
                name="street_address_recognizer",
                patterns=[
                    Pattern(
                        name="us_street_address_line",
                        # Matches: 742 Evergreen Terrace
                        regex=r"\b\d{1,6}\s+(?:[A-Za-z0-9'\.-]+\s+){1,6}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Terrace|Ter|Place|Pl|Parkway|Pkwy)\b",
                        score=0.75,
                    ),
                ],
            ),
            PatternRecognizer(
                supported_entity="US_ZIP_CODE",
                name="us_zip_code_recognizer",
                patterns=[
                    Pattern(
                        name="zip_after_state",
                        # Matches: IL 62704 / CA 94107 / NY 10001-1234
                        regex=r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s+\d{5}(?:-\d{4})?\b",
                        score=0.8,
                    ),
                    Pattern(
                        name="standalone_zip",
                        regex=r"\b\d{5}(?:-\d{4})?\b",
                        score=0.65,
                    ),
                ],
            ),
        ]

        for recognizer in custom_recognizers:
            self.analyzer.registry.add_recognizer(recognizer)

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
            entities=[
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
            ],
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
