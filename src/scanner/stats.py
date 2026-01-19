"""
Scanner Statistics Module

This module handles collecting, storing, and reporting scanner statistics.
Stats are stored in DynamoDB with a 7-day TTL for automatic cleanup.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.bot.db.dynamodb import save_scan_stats, get_stats_summary, get_latest_stats

logger = logging.getLogger(__name__)


@dataclass
class ScanStats:
    """
    Statistics for a single scanner run.
    
    Tracks all metrics needed for observability and debugging.
    """
    
    # Scan metrics
    searches_scanned: int = 0
    items_found: int = 0
    notifications_sent: int = 0
    
    # Request metrics
    requests_success: int = 0
    requests_failed: int = 0
    requests_blocked: int = 0
    
    # Detection method metrics
    detection_by_image: int = 0
    detection_by_api: int = 0
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    
    # Errors
    errors: list = field(default_factory=list)
    
    def start(self):
        """Mark the start of a scan run."""
        self.start_time = datetime.now(timezone.utc)
    
    def finish(self):
        """Mark the end of a scan run and calculate duration."""
        self.end_time = datetime.now(timezone.utc)
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def add_search_scanned(self):
        """Increment searches scanned counter."""
        self.searches_scanned += 1
    
    def add_items_found(self, count: int = 1):
        """Add to items found counter."""
        self.items_found += count
    
    def add_notification_sent(self):
        """Increment notifications sent counter."""
        self.notifications_sent += 1
    
    def add_request_success(self):
        """Increment successful requests counter."""
        self.requests_success += 1
    
    def add_request_failed(self):
        """Increment failed requests counter."""
        self.requests_failed += 1
    
    def add_request_blocked(self):
        """Increment blocked requests counter."""
        self.requests_blocked += 1
    
    def add_detection_by_image(self, count: int = 1):
        """Add to image URL detection counter."""
        self.detection_by_image += count
    
    def add_detection_by_api(self, count: int = 1):
        """Add to API detection counter."""
        self.detection_by_api += count
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary for storage."""
        return {
            "searches_scanned": self.searches_scanned,
            "items_found": self.items_found,
            "notifications_sent": self.notifications_sent,
            "requests_success": self.requests_success,
            "requests_failed": self.requests_failed,
            "requests_blocked": self.requests_blocked,
            "detection_by_image": self.detection_by_image,
            "detection_by_api": self.detection_by_api,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors[:10],  # Limit errors to prevent large payloads
        }
    
    @property
    def total_requests(self) -> int:
        """Total number of requests made."""
        return self.requests_success + self.requests_failed + self.requests_blocked
    
    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return round(self.requests_success / self.total_requests * 100, 1)
    
    @property
    def block_rate(self) -> float:
        """Block rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return round(self.requests_blocked / self.total_requests * 100, 1)
    
    @property
    def error_rate(self) -> float:
        """Error rate as a percentage."""
        if self.total_requests == 0:
            return 0.0
        return round(self.requests_failed / self.total_requests * 100, 1)
    
    def format_summary(self) -> str:
        """
        Format stats as a Telegram message summary.
        
        Returns:
            Formatted string for Telegram notification
        """
        lines = [
            "🔍 *Scanner Run Complete*",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📊 Searches: {self.searches_scanned} scanned",
            f"🆕 New Items: {self.items_found} found",
            f"📨 Notifications: {self.notifications_sent} sent",
            f"✅ Requests: {self.requests_success} success / {self.requests_failed + self.requests_blocked} failed",
            f"⏱️ Duration: {self.duration_seconds:.1f}s",
        ]
        
        # Add detection breakdown if items were found
        if self.items_found > 0:
            lines.append("")
            lines.append("📍 *Detection Method:*")
            lines.append(f"  • Image URL: {self.detection_by_image}")
            lines.append(f"  • API Call: {self.detection_by_api}")
        
        # Add warnings if there are issues
        if self.requests_blocked > 0:
            lines.append("")
            lines.append(f"⚠️ *Warning:* {self.requests_blocked} requests blocked")
        
        if self.errors:
            lines.append("")
            lines.append(f"❌ *Errors:* {len(self.errors)}")
            for error in self.errors[:3]:  # Show first 3 errors
                lines.append(f"  • {error[:50]}...")
        
        return "\n".join(lines)
    
    def check_alerts(self, block_threshold: float = 0.5, error_threshold: float = 0.2) -> list:
        """
        Check if any alert conditions are met.
        
        Args:
            block_threshold: Block rate threshold (0.0 - 1.0)
            error_threshold: Error rate threshold (0.0 - 1.0)
            
        Returns:
            List of alert messages
        """
        alerts = []
        
        if self.total_requests > 0:
            if self.block_rate / 100 > block_threshold:
                alerts.append(f"🚨 High block rate: {self.block_rate}% (threshold: {block_threshold * 100}%)")
            
            if self.error_rate / 100 > error_threshold:
                alerts.append(f"🚨 High error rate: {self.error_rate}% (threshold: {error_threshold * 100}%)")
        
        if self.searches_scanned == 0 and self.total_requests == 0:
            alerts.append("🚨 No scans completed - possible system issue")
        
        return alerts


async def save_stats(stats: ScanStats) -> bool:
    """
    Save scan statistics to DynamoDB.
    
    Args:
        stats: ScanStats object to save
        
    Returns:
        True if save was successful
    """
    return await save_scan_stats(stats.to_dict())


async def get_daily_summary() -> Dict[str, Any]:
    """
    Get today's aggregated stats summary.
    
    Returns:
        Dictionary with aggregated stats
    """
    return await get_stats_summary(days=1)


async def get_weekly_summary() -> Dict[str, Any]:
    """
    Get last 7 days aggregated stats summary.
    
    Returns:
        Dictionary with aggregated stats
    """
    return await get_stats_summary(days=7)


def format_summary_message(summary: Dict[str, Any], title: str = "Stats Summary") -> str:
    """
    Format a stats summary as a Telegram message.
    
    Args:
        summary: Stats summary dictionary
        title: Title for the message
        
    Returns:
        Formatted string for Telegram
    """
    if not summary:
        return "📊 No stats available"
    
    period = summary.get("period_days", 1)
    period_text = "Today" if period == 1 else f"Last {period} days"
    
    lines = [
        f"📊 *{title}*",
        f"📅 Period: {period_text}",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"🔄 Total Runs: {summary.get('total_runs', 0)}",
        f"📊 Searches Scanned: {summary.get('total_searches_scanned', 0)}",
        f"🆕 Items Found: {summary.get('total_items_found', 0)}",
        f"📨 Notifications Sent: {summary.get('total_notifications_sent', 0)}",
        "",
        "*Request Stats:*",
        f"  ✅ Success: {summary.get('total_requests_success', 0)} ({summary.get('success_rate', 0)}%)",
        f"  🚫 Blocked: {summary.get('total_requests_blocked', 0)} ({summary.get('block_rate', 0)}%)",
        f"  ❌ Failed: {summary.get('total_requests_failed', 0)} ({summary.get('error_rate', 0)}%)",
        "",
        "*Detection Method:*",
        f"  📷 Image URL: {summary.get('total_detection_by_image', 0)}",
        f"  🔗 API Call: {summary.get('total_detection_by_api', 0)}",
    ]
    
    return "\n".join(lines)