import logging
import fitz
import docx

logger = logging.getLogger(__name__)

class Redactor:
    """
    Applies permanent redactions to physical files after human approval.
    """
    
    @staticmethod
    def apply_pdf_redactions(input_path: str, output_path: str, approved_entities: list[str]) -> bool:
        """
        Uses PyMuPDF to draw permanent blackout boxes over matched PII strings.
        This actually removes the underlying font data from the PDF dictionary.
        """
        try:
            doc = fitz.open(input_path)
            # Remove exact duplicates from the list
            unique_entities = set(approved_entities)
            
            for page in doc:
                for entity_text in unique_entities:
                    # search_for returns a list of Rect objects where string is found
                    areas = page.search_for(entity_text)
                    for rect in areas:
                        # Add a redaction annotation (black color by default)
                        annot = page.add_redact_annot(rect, text="[REDACTED]")
                        
                # Actually permanently apply the redactions to the page content
                page.apply_redactions()
                
            # Save the document, removing any invisible text/garbage underneath
            doc.save(output_path, garbage=3, deflate=True)
            return True
            
        except Exception as e:
            logger.error(f"Failed PDF redaction: {e}")
            return False

    @staticmethod
    def apply_docx_redactions(input_path: str, output_path: str, approved_entities: list[str]) -> bool:
        """
        Iterates over DOCX paragraphs and tables, replacing matched PII with '[REDACTED]'.
        """
        try:
            doc = docx.Document(input_path)
            unique_entities = set(approved_entities)
            
            # Helper to replace text in runs to preserve some formatting
            def replace_text_in_runs(paragraphs):
                for p in paragraphs:
                    for entity_text in unique_entities:
                        if entity_text in p.text:
                            # A simple text replace on the paragraph level
                            p.text = p.text.replace(entity_text, "[REDACTED]")
                            
            # Process standard paragraphs
            replace_text_in_runs(doc.paragraphs)
            
            # Process table cells
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        replace_text_in_runs(cell.paragraphs)
                        
            doc.save(output_path)
            return True
            
        except Exception as e:
            logger.error(f"Failed DOCX redaction: {e}")
            return False

    @classmethod
    def redact(cls, input_path: str, output_path: str, approved_entities: list[str]) -> bool:
        """Auto format detection for redaction output."""
        if not approved_entities:
            logger.warning("No entities approved for redaction. Proceeding with copy.")
            
        if input_path.lower().endswith('.pdf'):
            return cls.apply_pdf_redactions(input_path, output_path, approved_entities)
        elif input_path.lower().endswith('.docx'):
            return cls.apply_docx_redactions(input_path, output_path, approved_entities)
        else:
            raise ValueError("Unsupported format.")
