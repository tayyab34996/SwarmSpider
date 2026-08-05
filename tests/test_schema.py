"""
Unit tests for SwarmSpider – schema/models.py
Tests cover: valid records, invalid price, empty title, optional description.
"""
import sys
import os
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from schema.models import ProductRecord


class TestProductRecord:
    def test_valid_record(self) -> None:
        record = ProductRecord(
            url="http://localhost/page/1",
            title="Widget A",
            price=9.99,
            in_stock=True,
            description="A fine widget"
        )
        assert record.url == "http://localhost/page/1"
        assert record.title == "Widget A"
        assert record.price == 9.99
        assert record.in_stock is True
        assert record.description == "A fine widget"

    def test_description_is_optional(self) -> None:
        record = ProductRecord(
            url="http://localhost/page/2",
            title="Widget B",
            price=4.50,
            in_stock=False
        )
        assert record.description is None

    def test_negative_price_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProductRecord(
                url="http://localhost/page/3",
                title="Cheap Thing",
                price=-1.00,
                in_stock=True
            )

    def test_empty_title_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProductRecord(
                url="http://localhost/page/4",
                title="",
                price=5.00,
                in_stock=True
            )

    def test_zero_price_is_valid(self) -> None:
        record = ProductRecord(
            url="http://localhost/page/5",
            title="Free Item",
            price=0.0,
            in_stock=True
        )
        assert record.price == 0.0

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProductRecord(url="http://localhost/page/6", title="No Price")  # type: ignore
