"""
Scanner Worker Module

This module provides the worker Lambda that processes a batch of searches.
It's invoked by the orchestrator Lambda with a subset of searches to scan.

Each worker Lambda instance gets a different IP address, helping to avoid
rate limiting from Yad2.
"""

import json
import logging
from typing import Any, Dict

from src.scanner.scanner import ItemScanner

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    AWS Lambda handler for the scanner worker.
    
    This handler is invoked by the orchestrator with a batch of searches
    to process. Each invocation runs in a separate Lambda instance with
    its own IP address.
    
    Args:
        event: Lambda event containing:
            - searches: List of search dictionaries to scan
            - batch_index: Index of this batch (for logging)
            - send_notification: Whether to send admin notification (default: False)
        context: AWS Lambda context object
    
    Returns:
        Dictionary with scan results summary
    """
    searches = event.get("searches", [])
    batch_index = event.get("batch_index", 0)
    # By default, don't send notification - orchestrator will send centralized one
    send_notification = event.get("send_notification", False)
    
    logger.info(
        f"Worker started - Batch {batch_index} with {len(searches)} searches"
    )
    
    if not searches:
        logger.warning("No searches provided to worker")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "No searches to process",
                "batch_index": batch_index,
            }),
        }
    
    # Log search names for debugging
    search_names = [s.get("name", s.get("id", "unknown")) for s in searches]
    logger.info(f"Processing searches: {search_names}")
    
    try:
        # Create scanner and process the batch
        scanner = ItemScanner()
        results = scanner.scan_batch_sync(
            searches=searches,
            batch_index=batch_index,
            lambda_context=context,
            send_admin_summary=send_notification,  # Controlled by orchestrator
        )
        
        logger.info(
            f"Batch {batch_index} completed: "
            f"{results.get('searches_scanned', 0)} searches, "
            f"{results.get('items_found', 0)} new items"
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Batch scan completed",
                "batch_index": batch_index,
                "results": results,
            }),
        }
        
    except Exception as e:
        logger.error(f"Error in batch {batch_index}: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "batch_index": batch_index,
            }),
        }