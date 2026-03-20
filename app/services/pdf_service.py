import pdfplumber
from app.utils.logger import logger
from app.utils.exceptions import FlowExecutionError
from io import BytesIO

class PDFService:
    @staticmethod
    def extract_text(file_content: bytes) -> str:
        """Extracts all text from a PDF file byte stream."""
        logger.info("PDFService: Extracting text from PDF...")
        try:
            with pdfplumber.open(BytesIO(file_content)) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
            
            if not full_text:
                logger.warning("PDFService: No text extracted from PDF.")
                return ""
                
            logger.info(f"PDFService: Extracted {len(full_text)} characters.")
            return full_text.strip()
        except Exception as e:
            logger.error(f"PDFService: Error extracting PDF: {str(e)}")
            raise FlowExecutionError(f"Failed to parse PDF file: {str(e)}")

pdf_service = PDFService()
