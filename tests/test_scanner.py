"""
Tests for the Scanner module.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.scanner.scanner import ItemScanner, scan_new_items
from src.scanner.notifier import TelegramNotifier
from src.yad2.parser import Yad2Item, SearchResult


class TestItemScanner:
    """Tests for ItemScanner class."""
    
    @pytest.fixture
    def mock_notifier(self):
        """Create a mock notifier."""
        notifier = Mock(spec=TelegramNotifier)
        notifier.notify_new_items = AsyncMock(return_value=True)
        return notifier
    
    @pytest.fixture
    def sample_items(self):
        """Create sample Yad2 items with created_at for detection."""
        now = datetime.now(timezone.utc)
        return [
            Yad2Item(
                id="item1",
                order_id=1,
                title="דירה 3 חדרים",
                price=5000,
                link="https://www.yad2.co.il/item/item1",
                location="תל אביב",
                created_at=now,
                created_at_source="image_url",
            ),
            Yad2Item(
                id="item2",
                order_id=2,
                title="דירה 4 חדרים",
                price=6000,
                link="https://www.yad2.co.il/item/item2",
                location="רמת גן",
                created_at=now,
                created_at_source="image_url",
            ),
        ]
    
    @pytest.fixture
    def sample_search(self):
        """Create a sample search."""
        return {
            "user_id": "123456",
            "id": "search-uuid-1",
            "name": "חיפוש תל אביב",
            "link": "https://www.yad2.co.il/realestate/rent?city=5000",
            "created_at": "2024-01-01T00:00:00",
            "last_scanned_at": "2024-01-14T00:00:00",
            "last_item_ids": ["old_item1", "old_item2"],
            "is_initial_scan_complete": True,
            "is_small_search": True,  # Use ID-bank-only detection
            "total_items": 10,
        }
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_all_searches_empty(self, mock_update, mock_get_all, mock_notifier):
        """Test scanning when there are no searches."""
        mock_get_all.return_value = []
        
        scanner = ItemScanner(notifier=mock_notifier)
        results = await scanner.scan_all_searches()
        
        # Results now use ScanStats.to_dict() keys
        assert results["searches_scanned"] == 0
        assert results["items_found"] == 0
        assert results["notifications_sent"] == 0
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_all_searches_with_new_items(
        self, mock_update, mock_get_all, mock_notifier, sample_search, sample_items
    ):
        """Test scanning with new items found (small search - ID-bank detection)."""
        mock_get_all.return_value = [sample_search]
        mock_update.return_value = True
        
        scanner = ItemScanner(notifier=mock_notifier)
        
        # Mock the parser to return sample items via get_search_result
        mock_result = SearchResult(items=sample_items, total_results=10)
        with patch.object(scanner.parser, 'get_search_result', return_value=mock_result):
            with patch.object(scanner.parser, 'get_items', return_value=[]):  # No additional pages
                results = await scanner.scan_all_searches()
        
        assert results["searches_scanned"] == 1
        assert results["items_found"] == 2  # Both items are new (not in last_item_ids)
        assert results["notifications_sent"] == 1
        
        # Verify notifier was called
        mock_notifier.notify_new_items.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_all_searches_no_new_items(
        self, mock_update, mock_get_all, mock_notifier, sample_search, sample_items
    ):
        """Test scanning when items already exist in last_item_ids."""
        # Set last_item_ids to include the sample items
        sample_search["last_item_ids"] = ["item1", "item2"]
        mock_get_all.return_value = [sample_search]
        mock_update.return_value = True
        
        scanner = ItemScanner(notifier=mock_notifier)
        
        mock_result = SearchResult(items=sample_items, total_results=10)
        with patch.object(scanner.parser, 'get_search_result', return_value=mock_result):
            with patch.object(scanner.parser, 'get_items', return_value=[]):
                results = await scanner.scan_all_searches()
        
        assert results["searches_scanned"] == 1
        assert results["items_found"] == 0
        assert results["notifications_sent"] == 0
        
        # Notifier should not be called when no new items
        mock_notifier.notify_new_items.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_single_search_updates_db(
        self, mock_update, mock_get_all, mock_notifier, sample_search, sample_items
    ):
        """Test that scan updates the database with new item IDs."""
        mock_get_all.return_value = [sample_search]
        mock_update.return_value = True
        
        scanner = ItemScanner(notifier=mock_notifier)
        
        mock_result = SearchResult(items=sample_items, total_results=10)
        with patch.object(scanner.parser, 'get_search_result', return_value=mock_result):
            with patch.object(scanner.parser, 'get_items', return_value=[]):
                await scanner.scan_all_searches()
        
        # Verify update was called with correct parameters
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args.kwargs["user_id"] == "123456"
        assert call_args.kwargs["search_id"] == "search-uuid-1"
        # Should include both old and new item IDs
        item_ids = call_args.kwargs["item_ids"]
        assert "item1" in item_ids
        assert "item2" in item_ids
        assert "old_item1" in item_ids
        assert "old_item2" in item_ids
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_handles_parser_error(
        self, mock_update, mock_get_all, mock_notifier, sample_search
    ):
        """Test that scanner handles parser errors gracefully."""
        mock_get_all.return_value = [sample_search]
        
        scanner = ItemScanner(notifier=mock_notifier)
        
        with patch.object(scanner.parser, 'get_search_result', side_effect=Exception("API Error")):
            results = await scanner.scan_all_searches()
        
        assert results["searches_scanned"] == 0  # Failed scan doesn't count
        assert len(results["errors"]) == 1
    
    @pytest.mark.asyncio
    @patch('src.scanner.scanner.get_all_searches')
    @patch('src.scanner.scanner.update_search_scan_results')
    async def test_scan_multiple_searches(
        self, mock_update, mock_get_all, mock_notifier, sample_items
    ):
        """Test scanning multiple searches (initial scans - no notifications)."""
        searches = [
            {
                "user_id": "user1",
                "id": "search1",
                "name": "Search 1",
                "link": "https://www.yad2.co.il/realestate/rent?city=5000",
                "last_scanned_at": None,
                "last_item_ids": [],
                "is_initial_scan_complete": False,  # Initial scan
            },
            {
                "user_id": "user2",
                "id": "search2",
                "name": "Search 2",
                "link": "https://www.yad2.co.il/realestate/rent?city=6000",
                "last_scanned_at": None,
                "last_item_ids": [],
                "is_initial_scan_complete": False,  # Initial scan
            },
        ]
        mock_get_all.return_value = searches
        mock_update.return_value = True
        
        scanner = ItemScanner(notifier=mock_notifier)
        
        mock_result = SearchResult(items=sample_items, total_results=10)
        with patch.object(scanner.parser, 'get_search_result', return_value=mock_result):
            with patch.object(scanner.parser, 'get_items', return_value=[]):
                results = await scanner.scan_all_searches()
        
        assert results["searches_scanned"] == 2
        # Initial scans don't send notifications
        assert results["items_found"] == 0
        assert results["notifications_sent"] == 0


class TestTelegramNotifier:
    """Tests for TelegramNotifier class."""
    
    @pytest.fixture
    def sample_items(self):
        """Create sample Yad2 items."""
        return [
            Yad2Item(
                id="item1",
                order_id=1,
                title="דירה 3 חדרים",
                price=5000,
                link="https://www.yad2.co.il/item/item1",
                location="תל אביב",
            ),
        ]
    
    def test_format_item_message(self):
        """Test item message formatting."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            notifier = TelegramNotifier()
            
            item = Yad2Item(
                id="item1",
                order_id=1,
                title="דירה יפה",
                price=5000,
                link="https://www.yad2.co.il/item/item1",
                location="תל אביב",
            )
            
            message = notifier._format_item_message(item)
            
            assert "דירה יפה" in message
            assert "5,000" in message
            assert "https://www.yad2.co.il/item/item1" in message
    
    def test_escape_markdown(self):
        """Test Markdown escaping."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            notifier = TelegramNotifier()
            
            text = "Test *bold* and _italic_"
            escaped = notifier._escape_markdown(text)
            
            assert "\\*" in escaped
            assert "\\_" in escaped
    
    @pytest.mark.asyncio
    async def test_notify_new_items_empty(self):
        """Test notification with empty items list."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            notifier = TelegramNotifier()
            
            result = await notifier.notify_new_items("123", "Test Search", [])
            
            assert result is True
    
    @pytest.mark.asyncio
    @patch('requests.Session.post')
    async def test_notify_new_items_success(self, mock_post, sample_items):
        """Test successful notification."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response
        
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            notifier = TelegramNotifier()
            
            result = await notifier.notify_new_items("123", "Test Search", sample_items)
            
            assert result is True
            # Should be called twice: once for header, once for item
            assert mock_post.call_count == 2


class TestScanNewItems:
    """Tests for scan_new_items function."""
    
    @patch.object(ItemScanner, 'scan_all_searches_sync')
    def test_scan_new_items(self, mock_scan):
        """Test scan_new_items function."""
        mock_scan.return_value = {
            "total_searches": 5,
            "successful_scans": 5,
            "new_items_found": 10,
        }
        
        results = scan_new_items()
        
        assert results["total_searches"] == 5
        mock_scan.assert_called_once()