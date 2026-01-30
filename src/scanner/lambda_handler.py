"""
Lambda Handler for the Scanner Job

This module provides the AWS Lambda entry point for the scheduled scanner job.
Includes timezone-aware scheduling to only run between 6 AM - 12 AM Israel time.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from src.config import settings
from src.scanner.scanner import ItemScanner

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Israel timezone
ISRAEL_TZ = ZoneInfo(settings.TIMEZONE)


def is_within_scan_hours() -> bool:
    """
    Check if current time is within allowed scan hours (Israel timezone).
    
    Returns:
        True if current time is between SCAN_START_HOUR and SCAN_END_HOUR
    """
    now_israel = datetime.now(ISRAEL_TZ)
    current_hour = now_israel.hour
    
    # Handle the case where end hour is 24 (midnight)
    if settings.SCAN_END_HOUR == 24:
        return current_hour >= settings.SCAN_START_HOUR
    else:
        return settings.SCAN_START_HOUR <= current_hour < settings.SCAN_END_HOUR


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for the scanner job.
    
    This function is triggered by CloudWatch Events on a schedule
    (e.g., every 30 minutes). It checks if the current time is within
    the allowed scan hours (6 AM - 12 AM Israel time) before running.
    
    Args:
        event: Lambda event (from CloudWatch Events)
        context: Lambda context
        
    Returns:
        Response with scan results or skip message
    """
    logger.info("Scanner Lambda triggered")
    logger.info(f"Event: {json.dumps(event)}")
    
    # Get current Israel time for logging
    now_israel = datetime.now(ISRAEL_TZ)
    logger.info(f"Current Israel time: {now_israel.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Check if we're within scan hours
    if not is_within_scan_hours():
        logger.info(
            f"Outside scan hours ({settings.SCAN_START_HOUR}:00 - {settings.SCAN_END_HOUR}:00 Israel time). "
            f"Current hour: {now_israel.hour}. Skipping scan."
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Scan skipped - outside scan hours",
                "current_hour_israel": now_israel.hour,
                "scan_hours": f"{settings.SCAN_START_HOUR}:00 - {settings.SCAN_END_HOUR}:00",
            }),
        }
    
    logger.info(f"Within scan hours. Starting scan...")
    
    try:
        scanner = ItemScanner()
        results = scanner.scan_all_searches_sync(lambda_context=context)
        
        logger.info(f"Scan completed: {json.dumps(results)}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Scan completed successfully",
                "results": results,
                "israel_time": now_israel.isoformat(),
            }),
        }
        
    except Exception as e:
        logger.error(f"Scanner error: {e}", exc_info=True)
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Scan failed",
                "error": str(e),
                "israel_time": now_israel.isoformat(),
            }),
        }