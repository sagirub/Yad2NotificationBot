#!/usr/bin/env python3
"""
Script to monitor the scale test results.

This script queries the stats table to show how the scanner is performing
with 100 searches over time.

Usage:
    # Show current status:
    python scripts/monitor_scale_test.py
    
    # Show detailed stats for today:
    python scripts/monitor_scale_test.py --detailed
    
    # Show stats for last 7 days:
    python scripts/monitor_scale_test.py --days 7
    
    # Watch mode (refresh every 5 minutes):
    python scripts/monitor_scale_test.py --watch
    
    # Export stats to CSV:
    python scripts/monitor_scale_test.py --export stats.csv
"""

import argparse
import asyncio
import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import boto3
from botocore.exceptions import ClientError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_dynamodb_tables(stage: str = "dev"):
    """Get DynamoDB table resources."""
    searches_table_name = f"yad2-notification-bot-{stage}-searches"
    stats_table_name = f"yad2-notification-bot-{stage}-stats"
    
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    region = os.environ.get("AWS_REGION", "eu-central-1")
    
    if endpoint_url:
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
        )
    else:
        dynamodb = boto3.resource("dynamodb", region_name=region)
    
    return {
        "searches": dynamodb.Table(searches_table_name),
        "stats": dynamodb.Table(stats_table_name),
    }


def count_searches(table) -> Dict[str, int]:
    """Count searches in the database."""
    response = table.scan(Select="COUNT")
    total = response.get("Count", 0)
    
    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(
            Select="COUNT",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        total += response.get("Count", 0)
    
    return {"total": total}


def get_stats_for_period(table, days: int = 1) -> List[Dict[str, Any]]:
    """Get all stats records for the specified period."""
    now = datetime.now(timezone.utc)
    all_items = []
    
    for i in range(days):
        date = now - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        
        try:
            response = table.query(
                KeyConditionExpression="stat_date = :date",
                ExpressionAttributeValues={":date": date_str},
            )
            all_items.extend(response.get("Items", []))
        except ClientError as e:
            print(f"Error querying stats for {date_str}: {e}")
    
    # Sort by timestamp
    all_items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_items


def aggregate_stats(stats_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate stats from multiple records."""
    if not stats_list:
        return {}
    
    aggregated = {
        "total_runs": len(stats_list),
        "total_searches_scanned": 0,
        "total_items_found": 0,
        "total_notifications_sent": 0,
        "total_requests_success": 0,
        "total_requests_failed": 0,
        "total_requests_blocked": 0,
        "total_detection_by_image": 0,
        "total_detection_by_api": 0,
        "total_duration_seconds": 0,
        "total_lambda_gb_seconds": 0,
        "blocked_searches": [],
        "errors": [],
        "first_run": None,
        "last_run": None,
    }
    
    for stat in stats_list:
        aggregated["total_searches_scanned"] += int(stat.get("searches_scanned", 0))
        aggregated["total_items_found"] += int(stat.get("items_found", 0))
        aggregated["total_notifications_sent"] += int(stat.get("notifications_sent", 0))
        aggregated["total_requests_success"] += int(stat.get("requests_success", 0))
        aggregated["total_requests_failed"] += int(stat.get("requests_failed", 0))
        aggregated["total_requests_blocked"] += int(stat.get("requests_blocked", 0))
        aggregated["total_detection_by_image"] += int(stat.get("detection_by_image", 0))
        aggregated["total_detection_by_api"] += int(stat.get("detection_by_api", 0))
        aggregated["total_duration_seconds"] += float(stat.get("duration_seconds", 0))
        aggregated["total_lambda_gb_seconds"] += float(stat.get("lambda_gb_seconds", 0))
        
        blocked = stat.get("blocked_searches", [])
        if blocked:
            aggregated["blocked_searches"].extend(blocked)
        
        errors = stat.get("errors", [])
        if errors:
            aggregated["errors"].extend(errors)
    
    # Get first and last run times
    if stats_list:
        timestamps = [s.get("timestamp", "") for s in stats_list if s.get("timestamp")]
        if timestamps:
            aggregated["first_run"] = min(timestamps)
            aggregated["last_run"] = max(timestamps)
    
    # Calculate rates
    total_requests = (
        aggregated["total_requests_success"] +
        aggregated["total_requests_failed"] +
        aggregated["total_requests_blocked"]
    )
    
    if total_requests > 0:
        aggregated["success_rate"] = round(aggregated["total_requests_success"] / total_requests * 100, 1)
        aggregated["block_rate"] = round(aggregated["total_requests_blocked"] / total_requests * 100, 1)
        aggregated["error_rate"] = round(aggregated["total_requests_failed"] / total_requests * 100, 1)
    else:
        aggregated["success_rate"] = 0
        aggregated["block_rate"] = 0
        aggregated["error_rate"] = 0
    
    # Calculate averages
    if aggregated["total_runs"] > 0:
        aggregated["avg_searches_per_run"] = round(
            aggregated["total_searches_scanned"] / aggregated["total_runs"], 1
        )
        aggregated["avg_duration_seconds"] = round(
            aggregated["total_duration_seconds"] / aggregated["total_runs"], 1
        )
        aggregated["avg_items_per_run"] = round(
            aggregated["total_items_found"] / aggregated["total_runs"], 2
        )
    
    return aggregated


def format_summary(aggregated: Dict[str, Any], search_count: int, days: int) -> str:
    """Format aggregated stats as a readable summary."""
    if not aggregated:
        return "No stats available for the specified period."
    
    lines = [
        "",
        "=" * 60,
        f"📊 SCALE TEST MONITORING REPORT",
        f"📅 Period: Last {days} day(s)",
        "=" * 60,
        "",
        "📋 DATABASE STATUS:",
        f"   Total searches in DB: {search_count}",
        "",
        "🔄 SCANNER RUNS:",
        f"   Total runs: {aggregated.get('total_runs', 0)}",
        f"   First run: {aggregated.get('first_run', 'N/A')}",
        f"   Last run: {aggregated.get('last_run', 'N/A')}",
        "",
        "📊 SCAN METRICS:",
        f"   Searches scanned: {aggregated.get('total_searches_scanned', 0)}",
        f"   Avg searches/run: {aggregated.get('avg_searches_per_run', 0)}",
        f"   New items found: {aggregated.get('total_items_found', 0)}",
        f"   Avg items/run: {aggregated.get('avg_items_per_run', 0)}",
        f"   Notifications sent: {aggregated.get('total_notifications_sent', 0)}",
        "",
        "🌐 REQUEST METRICS:",
        f"   Success: {aggregated.get('total_requests_success', 0)} ({aggregated.get('success_rate', 0)}%)",
        f"   Blocked: {aggregated.get('total_requests_blocked', 0)} ({aggregated.get('block_rate', 0)}%)",
        f"   Failed: {aggregated.get('total_requests_failed', 0)} ({aggregated.get('error_rate', 0)}%)",
        "",
        "📍 DETECTION METHOD:",
        f"   Image URL: {aggregated.get('total_detection_by_image', 0)}",
        f"   API Call: {aggregated.get('total_detection_by_api', 0)}",
        "",
        "⏱️ PERFORMANCE:",
        f"   Total duration: {aggregated.get('total_duration_seconds', 0):.1f}s",
        f"   Avg duration/run: {aggregated.get('avg_duration_seconds', 0):.1f}s",
        "",
        "☁️ LAMBDA USAGE:",
        f"   Total GB-seconds: {aggregated.get('total_lambda_gb_seconds', 0):.4f}",
        f"   Free tier used: {(aggregated.get('total_lambda_gb_seconds', 0) / 400000) * 100:.4f}%",
    ]
    
    # Add warnings
    if aggregated.get("block_rate", 0) > 20:
        lines.append("")
        lines.append("⚠️  WARNING: High block rate detected!")
        blocked_searches = aggregated.get("blocked_searches", [])
        if blocked_searches:
            unique_blocked = list(set(blocked_searches))[:10]
            lines.append(f"   Blocked searches: {', '.join(unique_blocked)}")
    
    if aggregated.get("errors"):
        lines.append("")
        lines.append(f"❌ ERRORS: {len(aggregated['errors'])} total")
        for error in aggregated["errors"][:5]:
            lines.append(f"   • {str(error)[:60]}...")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def format_detailed_stats(stats_list: List[Dict[str, Any]]) -> str:
    """Format individual stats records."""
    if not stats_list:
        return "No stats records found."
    
    lines = [
        "",
        "📊 DETAILED STATS (Most Recent First)",
        "=" * 80,
    ]
    
    for stat in stats_list[:20]:  # Show last 20 runs
        timestamp = stat.get("timestamp", "Unknown")
        if "T" in timestamp:
            display_time = timestamp.replace("T", " ")[:19]
        else:
            display_time = timestamp
        
        searches = stat.get("searches_scanned", 0)
        items = stat.get("items_found", 0)
        success = stat.get("requests_success", 0)
        blocked = stat.get("requests_blocked", 0)
        failed = stat.get("requests_failed", 0)
        duration = float(stat.get("duration_seconds", 0))
        
        # Status indicator
        if blocked > 0:
            status = "🚫"
        elif failed > 0:
            status = "⚠️"
        elif items > 0:
            status = "🆕"
        else:
            status = "✅"
        
        lines.append(
            f"{status} {display_time} | "
            f"Searches: {searches:3d} | "
            f"Items: {items:2d} | "
            f"Req: ✅{success}/🚫{blocked}/❌{failed} | "
            f"Duration: {duration:5.1f}s"
        )
    
    if len(stats_list) > 20:
        lines.append(f"... and {len(stats_list) - 20} more records")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def export_to_csv(stats_list: List[Dict[str, Any]], filename: str):
    """Export stats to CSV file."""
    if not stats_list:
        print("No stats to export.")
        return
    
    fieldnames = [
        "timestamp", "stat_date", "stat_hour",
        "searches_scanned", "items_found", "notifications_sent",
        "requests_success", "requests_failed", "requests_blocked",
        "detection_by_image", "detection_by_api",
        "duration_seconds", "lambda_gb_seconds",
    ]
    
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for stat in stats_list:
            # Convert Decimal to float for CSV
            row = {k: float(v) if hasattr(v, "__float__") else v for k, v in stat.items()}
            writer.writerow(row)
    
    print(f"✅ Exported {len(stats_list)} records to {filename}")


def watch_mode(tables: Dict, stage: str, interval: int = 300):
    """Continuously monitor stats."""
    print(f"👀 Watch mode enabled. Refreshing every {interval} seconds. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Clear screen
            os.system("clear" if os.name == "posix" else "cls")
            
            # Get current stats
            search_count = count_searches(tables["searches"])["total"]
            stats_list = get_stats_for_period(tables["stats"], days=1)
            aggregated = aggregate_stats(stats_list)
            
            # Print summary
            print(format_summary(aggregated, search_count, 1))
            print(f"\n🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Next refresh in {interval} seconds...")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\n👋 Watch mode stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor scale test results"
    )
    parser.add_argument(
        "--stage",
        default="dev",
        help="Deployment stage (dev, prod)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to include in stats (default: 1)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed stats for each run",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode - refresh every 5 minutes",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Refresh interval in seconds for watch mode (default: 300)",
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export stats to CSV file",
    )
    
    args = parser.parse_args()
    
    try:
        tables = get_dynamodb_tables(args.stage)
        
        if args.watch:
            watch_mode(tables, args.stage, args.interval)
            return
        
        # Get search count
        search_count = count_searches(tables["searches"])["total"]
        
        # Get stats
        stats_list = get_stats_for_period(tables["stats"], args.days)
        
        if args.export:
            export_to_csv(stats_list, args.export)
            return
        
        # Aggregate and display
        aggregated = aggregate_stats(stats_list)
        print(format_summary(aggregated, search_count, args.days))
        
        if args.detailed:
            print(format_detailed_stats(stats_list))
        
    except ClientError as e:
        print(f"❌ DynamoDB error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()