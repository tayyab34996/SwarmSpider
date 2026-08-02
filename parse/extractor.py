from bs4 import BeautifulSoup
from schema.models import ProductRecord
from pydantic import ValidationError
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class Extractor:
    def extract_and_validate(self, html: str, url: str) -> Tuple[Optional[ProductRecord], Optional[str]]:
        """
        Parses HTML and validates against ProductRecord.
        Returns (record, None) on success.
        Returns (None, error_reason) on failure.
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            title_el = soup.find(id='title')
            price_el = soup.find(id='price')
            stock_el = soup.find(id='stock')
            desc_el = soup.find(id='description')
            
            if not (title_el and price_el and stock_el):
                return None, "Missing required elements in HTML (title, price, or stock)"
                
            title = title_el.text.strip()
            
            # Basic cleanup for price to handle '$1.50' -> '1.50'
            price_str = price_el.text.replace('$', '').replace(',', '').strip()
            try:
                price_val = float(price_str)
            except ValueError:
                return None, f"Invalid price format: {price_str}"
                
            in_stock = stock_el.text.strip().lower() == "in stock"
            desc = desc_el.text.strip() if desc_el else None
            
            # Pydantic validation isolates bad data from the database
            record = ProductRecord(
                url=url,
                title=title,
                price=price_val,
                in_stock=in_stock,
                description=desc
            )
            return record, None
            
        except ValidationError as ve:
            logger.warning(f"Validation error for {url}: {ve}")
            return None, f"Validation failed"
        except Exception as e:
            logger.error(f"Extraction crash for {url}: {e}")
            return None, f"Extraction crashed: {str(e)}"
