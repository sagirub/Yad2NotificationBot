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

# AWS Lambda Free Tier Limits (per month)
LAMBDA_FREE_TIER_INVOCATIONS = 1_000_000  # 1 million requests
LAMBDA_FREE_TIER_GB_SECONDS = 400_000  # 400,000 GB-seconds


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
    detection_by_id_bank: int = 0  # Small searches: ID-bank-only detection
    detection_by_image: int = 0    # Large searches: createdAt from image URL
    detection_by_api: int = 0      # Large searches: createdAt from API call
    
    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    
    # Lambda usage metrics
    lambda_memory_mb: int = 0  # Memory allocated to Lambda
    lambda_billed_duration_ms: int = 0  # Billed duration in milliseconds
    
    # Blocked searches tracking
    blocked_searches: list = field(default_factory=list)  # List of search names that were blocked
    
    # Errors
    errors: list = field(default_factory=list)
    
    def start(self):
        """Mark the start of a scan run."""
        self.start_time = datetime.now(timezone.utc)
    
    def finish(self, context=None):
        """
        Mark the end of a scan run and calculate duration.
        
        Args:
            context: Lambda context object (optional) for extracting memory info
        """
        self.end_time = datetime.now(timezone.utc)
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        
        # Extract Lambda context info if available
        if context:
            try:
                # Memory limit in MB
                self.lambda_memory_mb = int(context.memory_limit_in_mb)
                # Remaining time can help calculate billed duration
                # Billed duration is rounded up to nearest 1ms (minimum 1ms)
                self.lambda_billed_duration_ms = max(1, int(self.duration_seconds * 1000))
            except (AttributeError, TypeError):
                pass
    
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
    
    def add_request_blocked(self, search_name: str = None):
        """
        Increment blocked requests counter.
        
        Args:
            search_name: Name of the search that was blocked (optional)
        """
        self.requests_blocked += 1
        if search_name and search_name not in self.blocked_searches:
            self.blocked_searches.append(search_name)
    
    def add_detection_by_id_bank(self, count: int = 1):
        """Add to ID-bank detection counter (small searches)."""
        self.detection_by_id_bank += count
    
    def add_detection_by_image(self, count: int = 1):
        """Add to image URL detection counter (large searches)."""
        self.detection_by_image += count
    
    def add_detection_by_api(self, count: int = 1):
        """Add to API detection counter (large searches)."""
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
            "detection_by_id_bank": self.detection_by_id_bank,
            "detection_by_image": self.detection_by_image,
            "detection_by_api": self.detection_by_api,
            "duration_seconds": round(self.duration_seconds, 2),
            "lambda_memory_mb": self.lambda_memory_mb,
            "lambda_billed_duration_ms": self.lambda_billed_duration_ms,
            "lambda_gb_seconds": self.lambda_gb_seconds,
            "blocked_searches": self.blocked_searches[:10],  # Limit to prevent large payloads
            "errors": self.errors[:10],  # Limit errors to prevent large payloads
        }
    
    @property
    def lambda_gb_seconds(self) -> float:
        """Calculate GB-seconds used by this Lambda invocation."""
        if self.lambda_memory_mb == 0 or self.lambda_billed_duration_ms == 0:
            return 0.0
        # GB-seconds = (memory in GB) × (duration in seconds)
        memory_gb = self.lambda_memory_mb / 1024
        duration_seconds = self.lambda_billed_duration_ms / 1000
        return round(memory_gb * duration_seconds, 4)
    
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
        
        # Add Lambda usage info
        if self.lambda_memory_mb > 0:
            lines.append("")
            lines.append("☁️ *Lambda Usage:*")
            lines.append(f"  • Memory: {self.lambda_memory_mb} MB")
            lines.append(f"  • GB-seconds: {self.lambda_gb_seconds:.4f}")
        
        # Add detection breakdown if items were found
        if self.items_found > 0:
            lines.append("")
            lines.append("📍 *Detection Method:*")
            lines.append(f"  • ID Bank (small): {self.detection_by_id_bank}")
            lines.append(f"  • Image URL (large): {self.detection_by_image}")
            lines.append(f"  • API Call (large): {self.detection_by_api}")
        
        # Add warnings if there are issues
        if self.requests_blocked > 0:
            lines.append("")
            lines.append(f"⚠️ *Warning:* {self.requests_blocked} requests blocked")
            if self.blocked_searches:
                lines.append("🚫 *Blocked Searches:*")
                for search_name in self.blocked_searches[:5]:  # Show first 5
                    lines.append(f"  • {search_name}")
        
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
    
    # Calculate Lambda usage percentages
    total_invocations = summary.get("total_runs", 0)
    total_gb_seconds = summary.get("total_lambda_gb_seconds", 0)
    
    invocations_pct = (total_invocations / LAMBDA_FREE_TIER_INVOCATIONS) * 100 if total_invocations > 0 else 0
    gb_seconds_pct = (total_gb_seconds / LAMBDA_FREE_TIER_GB_SECONDS) * 100 if total_gb_seconds > 0 else 0
    
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
        f"  🏦 ID Bank (small): {summary.get('total_detection_by_id_bank', 0)}",
        f"  📷 Image URL (large): {summary.get('total_detection_by_image', 0)}",
        f"  🔗 API Call (large): {summary.get('total_detection_by_api', 0)}",
        "",
        "☁️ *Lambda Free Tier Usage:*",
        f"  📞 Invocations: {total_invocations:,} / 1M ({invocations_pct:.2f}%)",
        f"  ⏱️ GB-seconds: {total_gb_seconds:,.2f} / 400K ({gb_seconds_pct:.2f}%)",
    ]
    
    # Add warning if approaching limits
    if invocations_pct > 80 or gb_seconds_pct > 80:
        lines.append("")
        lines.append("⚠️ *Warning: Approaching free tier limit!*")
    
    return "\n".join(lines)