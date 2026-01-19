"""
Tests for the Yad2 Parser module.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from src.yad2.parser import Yad2Parser, Yad2Item, get_items, get_item_ids


class TestYad2Item:
    """Tests for Yad2Item dataclass."""
    
    def test_from_next_data_valid(self):
        """Test creating Yad2Item from valid __NEXT_DATA__ item."""
        item_data = {
            "token": "abc123",
            "orderId": 12345,
            "price": 50000,
            "manufacturer": {"id": 46, "text": "פיג'ו"},
            "model": {"id": 10662, "text": "301"},
            "vehicleDates": {"yearOfProduction": 2017},
            "metaData": {"coverImage": "https://img.yad2.co.il/test.jpg"},
            "address": {"area": {"id": 4, "text": "פתח תקווה והסביבה"}},
            "hand": {"id": 2, "text": "יד שניה"},
            "adType": "private",
        }
        
        item = Yad2Item.from_next_data(item_data)
        
        assert item is not None
        assert item.id == "abc123"
        assert item.order_id == 12345
        assert item.price == 50000
        assert item.title == "פיג'ו 301 2017"
        assert item.manufacturer == "פיג'ו"
        assert item.model == "301"
        assert item.year == 2017
        assert item.location == "פתח תקווה והסביבה"
        assert item.hand == "יד שניה"
        assert item.image_url == "https://img.yad2.co.il/test.jpg"
        assert item.link == "https://www.yad2.co.il/item/abc123"
    
    def test_from_next_data_missing_token(self):
        """Test that missing token returns None."""
        item_data = {
            "orderId": 12345,
            "price": 50000,
        }
        
        item = Yad2Item.from_next_data(item_data)
        
        assert item is None
    
    def test_from_next_data_minimal(self):
        """Test creating item with minimal data."""
        item_data = {
            "token": "xyz789",
        }
        
        item = Yad2Item.from_next_data(item_data)
        
        assert item is not None
        assert item.id == "xyz789"
        assert item.title == "ללא כותרת"
        assert item.price is None
    
    def test_format_price(self):
        """Test price formatting."""
        item = Yad2Item(
            id="test",
            order_id=1,
            title="Test",
            price=50000,
            link="https://example.com",
        )
        
        assert item.format_price() == "₪50,000"
    
    def test_format_price_none(self):
        """Test price formatting when price is None."""
        item = Yad2Item(
            id="test",
            order_id=1,
            title="Test",
            price=None,
            link="https://example.com",
        )
        
        assert item.format_price() == "לא צוין מחיר"


class TestYad2Parser:
    """Tests for Yad2Parser class."""
    
    def test_validate_url_valid(self):
        """Test URL validation with valid URL."""
        parser = Yad2Parser()
        
        valid_url = "https://www.yad2.co.il/vehicles/cars?manufacturer=46"
        assert parser.validate_url(valid_url) is True
    
    def test_validate_url_invalid_netloc(self):
        """Test URL validation with invalid netloc."""
        parser = Yad2Parser()
        
        invalid_url = "https://www.example.com/vehicles/cars"
        assert parser.validate_url(invalid_url) is False
    
    def test_is_blocked_captcha(self):
        """Test bot protection detection - captcha."""
        parser = Yad2Parser()
        
        html = "<html><body>Please complete the CAPTCHA</body></html>"
        assert parser._is_blocked(html) is True
    
    def test_is_blocked_shieldsquare(self):
        """Test bot protection detection - ShieldSquare."""
        parser = Yad2Parser()
        
        html = "<html><body>ShieldSquare Captcha</body></html>"
        assert parser._is_blocked(html) is True
    
    def test_is_blocked_normal_page(self):
        """Test that normal page is not detected as blocked."""
        parser = Yad2Parser()
        
        html = "<html><body>Normal Yad2 page content</body></html>"
        assert parser._is_blocked(html) is False
    
    def test_extract_next_data_valid(self):
        """Test extracting __NEXT_DATA__ from HTML."""
        parser = Yad2Parser()
        
        next_data = {"props": {"pageProps": {}}}
        html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script></html>'
        
        result = parser._extract_next_data(html)
        
        assert result is not None
        assert result == next_data
    
    def test_extract_next_data_missing(self):
        """Test extracting __NEXT_DATA__ when not present."""
        parser = Yad2Parser()
        
        html = "<html><body>No next data here</body></html>"
        
        result = parser._extract_next_data(html)
        
        assert result is None
    
    def test_extract_next_data_invalid_json(self):
        """Test extracting __NEXT_DATA__ with invalid JSON."""
        parser = Yad2Parser()
        
        html = '<html><script id="__NEXT_DATA__" type="application/json">{invalid json}</script></html>'
        
        result = parser._extract_next_data(html)
        
        assert result is None
    
    def test_parse_items_from_next_data(self):
        """Test parsing items from __NEXT_DATA__ structure."""
        parser = Yad2Parser()
        
        next_data = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "queryKey": ["feed", "vehicles", "cars"],
                                "state": {
                                    "data": {
                                        "platinum": [],
                                        "boost": [],
                                        "solo": [],
                                        "commercial": [
                                            {
                                                "token": "item1",
                                                "orderId": 1,
                                                "price": 10000,
                                                "manufacturer": {"text": "Toyota"},
                                                "model": {"text": "Corolla"},
                                                "vehicleDates": {"yearOfProduction": 2020},
                                            }
                                        ],
                                        "private": [
                                            {
                                                "token": "item2",
                                                "orderId": 2,
                                                "price": 20000,
                                                "manufacturer": {"text": "Honda"},
                                                "model": {"text": "Civic"},
                                                "vehicleDates": {"yearOfProduction": 2019},
                                            }
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        items = parser._parse_items(next_data)
        
        assert len(items) == 2
        assert items[0].id == "item1"
        assert items[1].id == "item2"
    
    def test_parse_items_removes_duplicates(self):
        """Test that duplicate items are removed."""
        parser = Yad2Parser()
        
        next_data = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "queryKey": ["feed", "vehicles", "cars"],
                                "state": {
                                    "data": {
                                        "platinum": [
                                            {"token": "item1", "orderId": 1}
                                        ],
                                        "boost": [],
                                        "solo": [],
                                        "commercial": [
                                            {"token": "item1", "orderId": 1}  # Duplicate
                                        ],
                                        "private": [],
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        items = parser._parse_items(next_data)
        
        assert len(items) == 1
    
    @patch.object(Yad2Parser, '_extract_next_data')
    @patch('requests.Session.get')
    def test_get_items(self, mock_get, mock_extract):
        """Test fetching items."""
        parser = Yad2Parser()
        
        # Mock response
        mock_response = Mock()
        mock_response.text = "<html>...</html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        # Mock next data extraction
        mock_extract.return_value = {
            "props": {
                "pageProps": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "queryKey": ["feed", "vehicles", "cars"],
                                "state": {
                                    "data": {
                                        "platinum": [],
                                        "boost": [],
                                        "solo": [],
                                        "commercial": [],
                                        "private": [
                                            {"token": "test123", "orderId": 1, "price": 15000}
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        items = parser.get_items("https://www.yad2.co.il/vehicles/cars")
        
        assert len(items) == 1
        assert items[0].id == "test123"
    
    @patch('requests.Session.get')
    def test_get_items_blocked(self, mock_get):
        """Test handling blocked response."""
        parser = Yad2Parser()
        
        mock_response = Mock()
        mock_response.text = "<html>CAPTCHA required</html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        items = parser.get_items("https://www.yad2.co.il/vehicles/cars")
        
        assert len(items) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    @patch.object(Yad2Parser, 'get_items')
    def test_get_items_function(self, mock_get_items):
        """Test get_items function."""
        mock_items = [
            Yad2Item(
                id="1",
                order_id=1,
                title="Item 1",
                price=1000,
                link="https://www.yad2.co.il/item/1",
            ),
        ]
        mock_get_items.return_value = mock_items
        
        items = get_items("https://www.yad2.co.il/vehicles/cars")
        
        assert len(items) == 1
        mock_get_items.assert_called_once()
    
    @patch.object(Yad2Parser, 'get_item_ids')
    def test_get_item_ids_function(self, mock_get_ids):
        """Test get_item_ids function."""
        mock_get_ids.return_value = {"id1", "id2", "id3"}
        
        ids = get_item_ids("https://www.yad2.co.il/vehicles/cars")
        
        assert len(ids) == 3
        assert "id1" in ids
        mock_get_ids.assert_called_once()