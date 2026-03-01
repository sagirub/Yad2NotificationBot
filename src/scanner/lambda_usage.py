"""
Lambda Usage Module

Fetches real Lambda usage data from AWS CloudWatch to track free tier consumption.
AWS Lambda Free Tier (per month):
- 1,000,000 requests
- 400,000 GB-seconds of compute time
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import calendar

import boto3
from botocore.exceptions import ClientError

from src.config import LAMBDA_FREE_TIER_INVOCATIONS, LAMBDA_FREE_TIER_GB_SECONDS

logger = logging.getLogger(__name__)


def get_lambda_usage(function_name: str = None, region: str = None) -> Dict[str, Any]:
    """
    Get Lambda usage statistics from CloudWatch for the current month.
    
    Args:
        function_name: Lambda function name (optional, gets all if not specified)
        region: AWS region (optional, uses default)
        
    Returns:
        Dictionary with usage statistics
    """
    try:
        cloudwatch = boto3.client('cloudwatch', region_name=region or 'eu-central-1')
        
        # Get current month boundaries
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get last day of month
        _, last_day = calendar.monthrange(now.year, now.month)
        month_end = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        
        # Calculate days elapsed and remaining
        days_elapsed = (now - month_start).days + 1
        days_in_month = last_day
        days_remaining = days_in_month - days_elapsed + 1
        
        # Build dimensions for the query
        dimensions = []
        if function_name:
            dimensions = [{'Name': 'FunctionName', 'Value': function_name}]
        
        # Get invocation count
        invocations = _get_metric_sum(
            cloudwatch,
            metric_name='Invocations',
            namespace='AWS/Lambda',
            dimensions=dimensions,
            start_time=month_start,
            end_time=now,
        )
        
        # Get duration (in milliseconds)
        duration_ms = _get_metric_sum(
            cloudwatch,
            metric_name='Duration',
            namespace='AWS/Lambda',
            dimensions=dimensions,
            start_time=month_start,
            end_time=now,
        )
        
        # Get memory size to calculate GB-seconds
        # We'll estimate based on our Lambda config (512 MB)
        memory_mb = 512  # Default, could be fetched from Lambda config
        
        # Calculate GB-seconds: (memory in GB) × (duration in seconds)
        duration_seconds = duration_ms / 1000 if duration_ms else 0
        memory_gb = memory_mb / 1024
        gb_seconds = memory_gb * duration_seconds
        
        # Calculate percentages of free tier
        invocations_pct = (invocations / LAMBDA_FREE_TIER_INVOCATIONS) * 100 if invocations else 0
        gb_seconds_pct = (gb_seconds / LAMBDA_FREE_TIER_GB_SECONDS) * 100 if gb_seconds else 0
        
        # Estimate end-of-month usage based on current rate
        if days_elapsed > 0:
            daily_invocations = invocations / days_elapsed
            daily_gb_seconds = gb_seconds / days_elapsed
            
            estimated_invocations = invocations + (daily_invocations * days_remaining)
            estimated_gb_seconds = gb_seconds + (daily_gb_seconds * days_remaining)
            
            estimated_invocations_pct = (estimated_invocations / LAMBDA_FREE_TIER_INVOCATIONS) * 100
            estimated_gb_seconds_pct = (estimated_gb_seconds / LAMBDA_FREE_TIER_GB_SECONDS) * 100
        else:
            estimated_invocations = invocations
            estimated_gb_seconds = gb_seconds
            estimated_invocations_pct = invocations_pct
            estimated_gb_seconds_pct = gb_seconds_pct
        
        return {
            "month": now.strftime("%B %Y"),
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
            "days_in_month": days_in_month,
            
            # Current usage
            "invocations": int(invocations) if invocations else 0,
            "invocations_pct": round(invocations_pct, 2),
            "gb_seconds": round(gb_seconds, 2),
            "gb_seconds_pct": round(gb_seconds_pct, 2),
            
            # Estimated end-of-month
            "estimated_invocations": int(estimated_invocations),
            "estimated_invocations_pct": round(estimated_invocations_pct, 2),
            "estimated_gb_seconds": round(estimated_gb_seconds, 2),
            "estimated_gb_seconds_pct": round(estimated_gb_seconds_pct, 2),
            
            # Free tier limits
            "free_tier_invocations": LAMBDA_FREE_TIER_INVOCATIONS,
            "free_tier_gb_seconds": LAMBDA_FREE_TIER_GB_SECONDS,
            
            # Status
            "status": _get_usage_status(invocations_pct, gb_seconds_pct),
            "estimated_status": _get_usage_status(estimated_invocations_pct, estimated_gb_seconds_pct),
        }
        
    except ClientError as e:
        logger.error(f"Error fetching Lambda usage from CloudWatch: {e}")
        return {
            "error": str(e),
            "month": datetime.now(timezone.utc).strftime("%B %Y"),
        }
    except Exception as e:
        logger.error(f"Unexpected error fetching Lambda usage: {e}")
        return {
            "error": str(e),
            "month": datetime.now(timezone.utc).strftime("%B %Y"),
        }


def _get_metric_sum(
    cloudwatch,
    metric_name: str,
    namespace: str,
    dimensions: list,
    start_time: datetime,
    end_time: datetime,
) -> float:
    """
    Get the sum of a CloudWatch metric over a time period.
    """
    try:
        # Use a period that covers the entire month (in seconds)
        period = int((end_time - start_time).total_seconds()) + 1
        # CloudWatch requires period to be at least 60 seconds and a multiple of 60
        period = max(60, (period // 60) * 60)
        
        response = cloudwatch.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period,
            Statistics=['Sum'],
        )
        
        datapoints = response.get('Datapoints', [])
        if datapoints:
            return sum(dp.get('Sum', 0) for dp in datapoints)
        return 0
        
    except Exception as e:
        logger.warning(f"Error getting metric {metric_name}: {e}")
        return 0


def _get_usage_status(invocations_pct: float, gb_seconds_pct: float) -> str:
    """
    Get a status indicator based on usage percentages.
    """
    max_pct = max(invocations_pct, gb_seconds_pct)
    
    if max_pct >= 100:
        return "🔴 EXCEEDED"
    elif max_pct >= 80:
        return "🟠 WARNING"
    elif max_pct >= 50:
        return "🟡 MODERATE"
    else:
        return "🟢 OK"


def format_lambda_usage_message(usage: Dict[str, Any]) -> str:
    """
    Format Lambda usage as a Telegram message.
    
    Args:
        usage: Usage dictionary from get_lambda_usage()
        
    Returns:
        Formatted string for Telegram
    """
    if "error" in usage:
        return f"❌ Error fetching Lambda usage: {usage['error']}"
    
    lines = [
        "☁️ *Lambda Free Tier Usage*",
        f"📅 {usage['month']} (Day {usage['days_elapsed']}/{usage['days_in_month']})",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
        "*Current Usage:*",
        f"  📞 Invocations: {usage['invocations']:,} / 1M ({usage['invocations_pct']:.1f}%)",
        f"  ⏱️ GB-seconds: {usage['gb_seconds']:,.1f} / 400K ({usage['gb_seconds_pct']:.1f}%)",
        f"  Status: {usage['status']}",
        "",
        "*Estimated End of Month:*",
        f"  📞 Invocations: ~{usage['estimated_invocations']:,} ({usage['estimated_invocations_pct']:.1f}%)",
        f"  ⏱️ GB-seconds: ~{usage['estimated_gb_seconds']:,.1f} ({usage['estimated_gb_seconds_pct']:.1f}%)",
        f"  Status: {usage['estimated_status']}",
    ]
    
    # Add warning if approaching limits
    if usage['estimated_invocations_pct'] > 80 or usage['estimated_gb_seconds_pct'] > 80:
        lines.append("")
        lines.append("⚠️ *Warning: May exceed free tier this month!*")
    
    return "\n".join(lines)