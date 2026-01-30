#!/usr/bin/env python3
"""
Script to populate the DynamoDB table with 100 test searches for scale testing.

This script creates 100 searches distributed across multiple test users,
with varied Yad2 search URLs to simulate realistic usage patterns.

Usage:
    # For local DynamoDB (testing):
    DYNAMODB_ENDPOINT_URL=http://localhost:8000 python scripts/populate_test_searches.py
    
    # For AWS DynamoDB (production test):
    AWS_PROFILE=your-profile python scripts/populate_test_searches.py --stage dev
    
    # Clean up test data:
    python scripts/populate_test_searches.py --cleanup
"""

import argparse
import os
import sys
import uuid
import random
from datetime import datetime, timezone
from typing import List, Dict, Any

import boto3
from botocore.exceptions import ClientError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
NUM_SEARCHES = 100
NUM_TEST_USERS = 10  # Distribute searches across 10 test users
TEST_USER_ID_PREFIX = "test_user_"  # Prefix for test user IDs

# Yad2 search URL templates for cars
# These are real Yad2 URL patterns for vehicle searches
YAD2_SEARCH_TEMPLATES = [
    # Toyota
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19&year=2020-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19&year=2018-2022&price=50000-100000",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19&model=1282",  # Corolla
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19&model=1283",  # Camry
    "https://www.yad2.co.il/vehicles/cars?manufacturer=19&model=1284",  # Yaris
    
    # Hyundai
    "https://www.yad2.co.il/vehicles/cars?manufacturer=21",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=21&year=2019-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=21&price=40000-80000",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=21&model=1401",  # i20
    "https://www.yad2.co.il/vehicles/cars?manufacturer=21&model=1402",  # i30
    
    # Kia
    "https://www.yad2.co.il/vehicles/cars?manufacturer=28",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=28&year=2020-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=28&price=50000-120000",
    
    # Mazda
    "https://www.yad2.co.il/vehicles/cars?manufacturer=35",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=35&year=2018-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=35&model=1601",  # Mazda 3
    
    # Honda
    "https://www.yad2.co.il/vehicles/cars?manufacturer=20",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=20&year=2019-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=20&price=60000-150000",
    
    # Nissan
    "https://www.yad2.co.il/vehicles/cars?manufacturer=38",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=38&year=2018-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=38&model=1701",  # Qashqai
    
    # Volkswagen
    "https://www.yad2.co.il/vehicles/cars?manufacturer=47",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=47&year=2019-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=47&model=1901",  # Golf
    
    # Skoda
    "https://www.yad2.co.il/vehicles/cars?manufacturer=43",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=43&year=2020-2024",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=43&model=2001",  # Octavia
    
    # Seat
    "https://www.yad2.co.il/vehicles/cars?manufacturer=42",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=42&year=2019-2024",
    
    # Suzuki
    "https://www.yad2.co.il/vehicles/cars?manufacturer=44",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=44&year=2018-2024",
    
    # Mitsubishi
    "https://www.yad2.co.il/vehicles/cars?manufacturer=36",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=36&year=2019-2024",
    
    # Subaru
    "https://www.yad2.co.il/vehicles/cars?manufacturer=45",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=45&year=2018-2024",
    
    # BMW
    "https://www.yad2.co.il/vehicles/cars?manufacturer=9",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=9&year=2018-2024&price=100000-300000",
    
    # Mercedes
    "https://www.yad2.co.il/vehicles/cars?manufacturer=37",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=37&year=2019-2024",
    
    # Audi
    "https://www.yad2.co.il/vehicles/cars?manufacturer=7",
    "https://www.yad2.co.il/vehicles/cars?manufacturer=7&year=2018-2024",
    
    # Price range searches
    "https://www.yad2.co.il/vehicles/cars?price=20000-50000",
    "https://www.yad2.co.il/vehicles/cars?price=50000-100000",
    "https://www.yad2.co.il/vehicles/cars?price=100000-200000",
    "https://www.yad2.co.il/vehicles/cars?price=200000-500000",
    
    # Year range searches
    "https://www.yad2.co.il/vehicles/cars?year=2023-2024",
    "https://www.yad2.co.il/vehicles/cars?year=2022-2024",
    "https://www.yad2.co.il/vehicles/cars?year=2020-2024",
    "https://www.yad2.co.il/vehicles/cars?year=2018-2022",
    
    # Hand (ownership) searches
    "https://www.yad2.co.il/vehicles/cars?hand=1",  # First hand
    "https://www.yad2.co.il/vehicles/cars?hand=1&year=2020-2024",
    "https://www.yad2.co.il/vehicles/cars?hand=2",  # Second hand
    
    # Combined searches
    "https://www.yad2.co.il/vehicles/cars?year=2021-2024&price=80000-150000",
    "https://www.yad2.co.il/vehicles/cars?year=2020-2024&hand=1&price=100000-200000",
]

# Search name templates for cars
SEARCH_NAMES = [
    "{manufacturer} {year}",
    "חיפוש {manufacturer}",
    "רכב עד {price}₪",
    "{manufacturer} יד {hand}",
    "רכב שנת {year}",
]

MANUFACTURERS = [
    "טויוטה", "יונדאי", "קיה", "מאזדה", "הונדה",
    "ניסאן", "פולקסווגן", "סקודה", "סיאט", "סוזוקי",
    "מיצובישי", "סובארו", "BMW", "מרצדס", "אאודי"
]


def get_dynamodb_table(stage: str = "dev"):
    """Get DynamoDB table resource."""
    table_name = f"yad2-notification-bot-{stage}-searches"
    
    endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL")
    region = os.environ.get("AWS_REGION", "eu-central-1")
    
    if endpoint_url:
        print(f"Using local DynamoDB at {endpoint_url}")
        dynamodb = boto3.resource(
            "dynamodb",
            endpoint_url=endpoint_url,
            region_name=region,
        )
    else:
        print(f"Using AWS DynamoDB in region {region}")
        dynamodb = boto3.resource("dynamodb", region_name=region)
    
    return dynamodb.Table(table_name)


def generate_search_name(index: int) -> str:
    """Generate a realistic search name for cars."""
    template = random.choice(SEARCH_NAMES)
    manufacturer = random.choice(MANUFACTURERS)
    year = random.choice(["2020-2024", "2021-2024", "2022-2024", "2023-2024"])
    price = random.choice(["50,000", "100,000", "150,000", "200,000"])
    hand = random.choice(["ראשונה", "שנייה"])
    
    name = template.format(manufacturer=manufacturer, year=year, price=price, hand=hand)
    return f"{name} #{index + 1}"


def generate_test_searches(num_searches: int, num_users: int) -> List[Dict[str, Any]]:
    """Generate test search records."""
    searches = []
    
    for i in range(num_searches):
        # Distribute searches across users
        user_index = i % num_users
        user_id = f"{TEST_USER_ID_PREFIX}{user_index + 1}"
        
        # Pick a random search URL template
        search_url = random.choice(YAD2_SEARCH_TEMPLATES)
        
        # Add some variation to the URL (different page, sort order, etc.)
        variations = [
            "",
            "&order=1",  # Sort by date
            "&order=2",  # Sort by price
            "&imgOnly=1",  # Only with images
        ]
        search_url += random.choice(variations)
        
        search = {
            "user_id": user_id,
            "search_id": str(uuid.uuid4()),
            "name": generate_search_name(i),
            "link": search_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_scanned_at": None,
            "last_item_ids": [],
            "is_initial_scan_complete": False,
        }
        searches.append(search)
    
    return searches


def populate_searches(table, searches: List[Dict[str, Any]], batch_size: int = 25):
    """Write searches to DynamoDB in batches."""
    print(f"Writing {len(searches)} searches to DynamoDB...")
    
    # Use batch writer for efficient writes
    with table.batch_writer() as batch:
        for i, search in enumerate(searches):
            batch.put_item(Item=search)
            if (i + 1) % batch_size == 0:
                print(f"  Written {i + 1}/{len(searches)} searches...")
    
    print(f"✅ Successfully wrote {len(searches)} searches to DynamoDB")


def cleanup_test_searches(table):
    """Remove all test searches from the database."""
    print("Cleaning up test searches...")
    
    deleted_count = 0
    
    # Scan for test users
    for user_index in range(NUM_TEST_USERS):
        user_id = f"{TEST_USER_ID_PREFIX}{user_index + 1}"
        
        try:
            response = table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
            )
            
            items = response.get("Items", [])
            
            for item in items:
                table.delete_item(
                    Key={
                        "user_id": item["user_id"],
                        "search_id": item["search_id"],
                    }
                )
                deleted_count += 1
            
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.query(
                    KeyConditionExpression="user_id = :uid",
                    ExpressionAttributeValues={":uid": user_id},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                
                for item in response.get("Items", []):
                    table.delete_item(
                        Key={
                            "user_id": item["user_id"],
                            "search_id": item["search_id"],
                        }
                    )
                    deleted_count += 1
                    
        except ClientError as e:
            print(f"Error cleaning up user {user_id}: {e}")
    
    print(f"✅ Deleted {deleted_count} test searches")


def count_searches(table) -> Dict[str, int]:
    """Count total searches and test searches in the database."""
    total_count = 0
    test_count = 0
    
    response = table.scan(Select="COUNT")
    total_count = response.get("Count", 0)
    
    # Count test searches
    for user_index in range(NUM_TEST_USERS):
        user_id = f"{TEST_USER_ID_PREFIX}{user_index + 1}"
        
        try:
            response = table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                Select="COUNT",
            )
            test_count += response.get("Count", 0)
        except ClientError:
            pass
    
    return {
        "total": total_count,
        "test": test_count,
        "real": total_count - test_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Populate DynamoDB with test searches for scale testing"
    )
    parser.add_argument(
        "--stage",
        default="dev",
        help="Deployment stage (dev, prod)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=NUM_SEARCHES,
        help=f"Number of test searches to create (default: {NUM_SEARCHES})",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=NUM_TEST_USERS,
        help=f"Number of test users to distribute searches across (default: {NUM_TEST_USERS})",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove all test searches instead of creating them",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current search counts without making changes",
    )
    
    args = parser.parse_args()
    
    try:
        table = get_dynamodb_table(args.stage)
        
        # Show current status
        counts = count_searches(table)
        print(f"\n📊 Current database status:")
        print(f"   Total searches: {counts['total']}")
        print(f"   Test searches:  {counts['test']}")
        print(f"   Real searches:  {counts['real']}")
        print()
        
        if args.status:
            return
        
        if args.cleanup:
            cleanup_test_searches(table)
        else:
            # Generate and populate test searches
            searches = generate_test_searches(args.count, args.users)
            populate_searches(table, searches)
            
            # Show updated status
            counts = count_searches(table)
            print(f"\n📊 Updated database status:")
            print(f"   Total searches: {counts['total']}")
            print(f"   Test searches:  {counts['test']}")
            print(f"   Real searches:  {counts['real']}")
        
        print("\n✅ Done!")
        
    except ClientError as e:
        print(f"❌ DynamoDB error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()