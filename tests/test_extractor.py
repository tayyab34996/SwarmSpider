"""
Unit tests for SwarmSpider – parse/extractor.py
Tests cover: successful extraction, malformed HTML, bad price, validation failures.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from parse.extractor import Extractor
from schema.models import ProductRecord

extractor = Extractor()

GOOD_HTML = """
<html><body>
  <h1 id="title">Awesome Product 1</h1>
  <p id="price">$12.50</p>
  <p id="stock">In Stock</p>
  <div id="description">A great item</div>
</body></html>
"""

OUT_OF_STOCK_HTML = """
<html><body>
  <h1 id="title">Sold Out Widget</h1>
  <p id="price">$0.99</p>
  <p id="stock">Out of Stock</p>
</body></html>
"""

MALFORMED_HTML = "<html><body>Bad Data No Fields</body></html>"

BAD_PRICE_HTML = """
<html><body>
  <h1 id="title">Broken Pricing</h1>
  <p id="price">free!</p>
  <p id="stock">In Stock</p>
</body></html>
"""

MISSING_TITLE_HTML = """
<html><body>
  <p id="price">$5.00</p>
  <p id="stock">In Stock</p>
</body></html>
"""


class TestExtractor:
    def test_successful_extraction(self) -> None:
        record, err = extractor.extract_and_validate(GOOD_HTML, "http://test/page/1")
        assert err is None
        assert isinstance(record, ProductRecord)
        assert record.title == "Awesome Product 1"
        assert record.price == 12.50
        assert record.in_stock is True
        assert record.description == "A great item"
        assert record.url == "http://test/page/1"

    def test_out_of_stock_parsed_correctly(self) -> None:
        record, err = extractor.extract_and_validate(OUT_OF_STOCK_HTML, "http://test/page/2")
        assert err is None
        assert record is not None
        assert record.in_stock is False
        assert record.description is None  # no description element

    def test_malformed_html_returns_error(self) -> None:
        record, err = extractor.extract_and_validate(MALFORMED_HTML, "http://test/page/3")
        assert record is None
        assert err is not None
        assert "Missing required elements" in err

    def test_bad_price_returns_error(self) -> None:
        record, err = extractor.extract_and_validate(BAD_PRICE_HTML, "http://test/page/4")
        assert record is None
        assert err is not None
        assert "Invalid price format" in err

    def test_missing_title_returns_error(self) -> None:
        record, err = extractor.extract_and_validate(MISSING_TITLE_HTML, "http://test/page/5")
        assert record is None
        assert err is not None

    def test_price_with_dollar_sign_stripped(self) -> None:
        record, err = extractor.extract_and_validate(GOOD_HTML, "http://test/page/6")
        assert err is None
        assert record is not None
        assert record.price == 12.50  # $ was stripped correctly

    def test_empty_html_returns_error(self) -> None:
        record, err = extractor.extract_and_validate("", "http://test/page/7")
        assert record is None
        assert err is not None
