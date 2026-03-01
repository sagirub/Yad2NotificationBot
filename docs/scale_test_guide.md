# Scale Test Guide: 100 Searches for 24 Hours

This guide explains how to run a scale test with 100 searches to validate the scanner's performance at scale.

## Overview

The scale test will:
1. Populate the database with 100 test searches distributed across 10 test users
2. Let the scanner run for 24 hours (or longer)
3. Monitor performance metrics including:
   - Request success/failure/block rates
   - New items detection
   - Lambda usage and costs
   - Response times

## Prerequisites

1. **AWS Credentials**: Ensure you have AWS credentials configured
   ```bash
   aws configure
   # Or set environment variables:
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_REGION=eu-central-1
   ```

2. **Deployed Infrastructure**: The serverless stack must be deployed
   ```bash
   serverless deploy --stage dev
   ```

3. **Python Dependencies**: Install required packages
   ```bash
   poetry install
   # Or: pip install -r requirements.txt
   ```

## Step 1: Populate Test Searches

Run the populate script to add 100 test searches:

```bash
# Check current database status
python scripts/populate_test_searches.py --status

# Add 100 test searches (distributed across 10 test users)
python scripts/populate_test_searches.py --count 100 --users 10

# Verify the searches were added
python scripts/populate_test_searches.py --status
```

### Expected Output:
```
📊 Current database status:
   Total searches: 100
   Test searches:  100
   Real searches:  0

✅ Done!
```

### Customization Options:
- `--count N`: Number of test searches (default: 100)
- `--users N`: Number of test users to distribute across (default: 10)
- `--stage dev|prod`: Target environment (default: dev)

## Step 2: Verify Scanner Configuration

The scanner is configured to run every 30 minutes during scan hours (6 AM - midnight Israel time).

Check the current configuration in `serverless.yml`:
```yaml
searchOrchestrator:
  events:
    - schedule:
        rate: cron(0,30 3-21 * * ? *)
        enabled: true
```

### Key Settings:
- **Max Requests Per Worker**: 5 estimated HTTP requests per worker Lambda (configurable via `MAX_REQUESTS_PER_WORKER`)
- **Max Pages Initial**: 3 pages for first scan (large searches)
- **Max Pages Regular**: 1 page for subsequent scans
- **Max Safe Pages**: 5 (small searches needing more are reclassified as large)
- **Scan Hours**: 6 AM - midnight Israel time

## Step 3: Monitor the Test

### Real-time Monitoring

Use the monitoring script to track progress:

```bash
# Show current status
python scripts/monitor_scale_test.py

# Show detailed stats for each run
python scripts/monitor_scale_test.py --detailed

# Watch mode (auto-refresh every 5 minutes)
python scripts/monitor_scale_test.py --watch

# Show stats for last 7 days
python scripts/monitor_scale_test.py --days 7

# Export stats to CSV for analysis
python scripts/monitor_scale_test.py --export scale_test_results.csv
```

### Telegram Bot Commands

If you're the admin, use these commands in the Telegram bot:

```
/stats today    - Today's summary
/stats week     - Last 7 days summary
/stats recent   - Last 10 scan runs
/stats lambda   - AWS Lambda free tier usage
```

### CloudWatch Logs

View Lambda logs in AWS Console or CLI:

```bash
# View orchestrator logs
aws logs tail /aws/lambda/yad2-notification-bot-dev-searchOrchestrator --follow

# View worker logs
aws logs tail /aws/lambda/yad2-notification-bot-dev-searchWorker --follow
```

## Step 4: Analyze Results

After 24 hours, analyze the results:

```bash
# Get full summary
python scripts/monitor_scale_test.py --days 1

# Export for detailed analysis
python scripts/monitor_scale_test.py --days 1 --export day1_results.csv
```

### Key Metrics to Watch:

| Metric | Healthy Range | Warning | Critical |
|--------|---------------|---------|----------|
| Success Rate | > 90% | 70-90% | < 70% |
| Block Rate | < 10% | 10-30% | > 30% |
| Error Rate | < 5% | 5-15% | > 15% |
| Avg Duration | < 60s | 60-120s | > 120s |

### Expected Results for 100 Searches:

With 100 searches running every 30 minutes for 24 hours:
- **Total Runs**: ~48 runs (24 hours × 2 runs/hour, minus off-hours)
- **Searches per Run**: 100
- **Total Scans**: ~4,800 search scans
- **Batches per Run**: Varies based on request budget (regular scans: ~20 batches of 5 searches each)
- **Lambda Invocations**: ~1,000 (48 runs × ~21 invocations per run)

## Step 5: Cleanup

After the test, remove test data:

```bash
# Remove all test searches
python scripts/populate_test_searches.py --cleanup

# Verify cleanup
python scripts/populate_test_searches.py --status
```

## Troubleshooting

### High Block Rate

If you see a high block rate (> 30%):
1. Check if Yad2 is rate limiting
2. Consider reducing batch size
3. Add delays between requests
4. Check if specific search URLs are problematic

### Lambda Timeouts

If workers are timing out:
1. Increase `timeout` in `serverless.yml`
2. Reduce batch size
3. Check for slow network conditions

### No Stats Being Recorded

If stats aren't appearing:
1. Check CloudWatch logs for errors
2. Verify DynamoDB table permissions
3. Ensure stats table exists

### Test Users Receiving Notifications

Test users (IDs starting with `test_user_`) won't receive actual Telegram notifications since they're not real Telegram user IDs. The notification attempts will fail silently.

## Cost Estimation

For 100 searches running 24 hours:

### Lambda Costs (Free Tier):
- Invocations: ~1,680 (well within 1M free tier)
- GB-seconds: ~840 (512MB × ~1s × 1,680 = 840 GB-s, within 400K free tier)

### DynamoDB Costs (Free Tier):
- Read/Write: Minimal, within free tier
- Storage: < 1MB for 100 searches

### Total Estimated Cost: $0 (within free tier)

## Extending the Test

To run a longer test (e.g., 7 days):

1. Keep the test searches in place
2. Monitor daily using:
   ```bash
   python scripts/monitor_scale_test.py --days 7
   ```
3. Export weekly results:
   ```bash
   python scripts/monitor_scale_test.py --days 7 --export week_results.csv
   ```

## Scaling Beyond 100 Searches

To test with more searches:

```bash
# Add 500 searches across 50 users
python scripts/populate_test_searches.py --count 500 --users 50
```

Consider adjusting:
- `MAX_REQUESTS_PER_WORKER`: Increase to pack more searches per worker (reduces Lambda invocations but increases bot detection risk)
- Worker `timeout`: Increase for larger batches
- Orchestrator `timeout`: Increase to wait for more workers