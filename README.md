# Yad2 Notification Bot 🏠

A Telegram bot that monitors Yad2 (Israeli real estate website) searches and notifies you when new listings appear.

## Features

- 🔍 Track multiple Yad2 search URLs
- 🔔 Get notifications for new listings every 30 minutes
- 📋 Manage your searches via Telegram
- ☁️ Serverless deployment on AWS Lambda

---

## Quick Start

### Prerequisites

1. **Python 3.10+** installed
2. **Node.js 18+** installed (for Serverless Framework)
3. **Poetry** installed: `curl -sSL https://install.python-poetry.org | python3 -`
4. **AWS CLI** configured: `aws configure`
5. **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)

---

## 🖥️ Local Development (Polling Mode)

Use this for development and testing on your local machine.

### 1. Install Dependencies

```bash
# Install Python dependencies
poetry install

# Install Node.js dependencies (for serverless)
npm install
```

### 2. Configure Environment

```bash
# Copy example and edit with your bot token
cp .env.example .env
nano .env
```

Your `.env` file:
```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
AWS_REGION=eu-central-1
```

### 3. Run the Bot

```bash
poetry run python -m src.bot.run_polling
```

You should see:
```
🤖 Bot started (polling mode)... Press CTRL+C to stop
```

### 4. Test in Telegram

1. Open Telegram and find your bot
2. Send `/start`
3. Use the menu buttons!

---

## 🚀 Deploy to AWS Lambda

Deploy the bot to AWS so it runs 24/7 without your computer.

### What is a "Stage"?

A **stage** is an environment for your deployment:

| Stage | Purpose | Use Case |
|-------|---------|----------|
| `dev` | Development/Testing | Test changes before production |
| `production` | Live/Production | Real users, stable version |

Each stage creates separate AWS resources (Lambda functions, DynamoDB tables, etc.) so they don't interfere with each other.

### One-Command Deployment

The webhook is **automatically set** after deployment!

```bash
# Set your bot token and deploy
export TELEGRAM_BOT_TOKEN=your_token_here
serverless deploy --stage dev
```

That's it! The deployment will:
1. ✅ Package your code
2. ✅ Upload to AWS Lambda
3. ✅ Create API Gateway endpoint
4. ✅ Create DynamoDB table
5. ✅ **Automatically set the Telegram webhook**

### Deployment Output

After deployment, you'll see:
```
✔ Service deployed to stack yad2-notification-bot-dev

endpoints:
  POST - https://abc123.execute-api.eu-central-1.amazonaws.com/webhook
  GET - https://abc123.execute-api.eu-central-1.amazonaws.com/health

Setting Telegram webhook...
✅ Webhook set!
```

### Deploy to Production

```bash
export TELEGRAM_BOT_TOKEN=your_token_here
serverless deploy --stage production
```

---

## 📋 Useful Commands

### Local Development

```bash
# Run bot locally (polling mode)
poetry run python -m src.bot.run_polling

# Run tests
poetry run pytest
```

### Deployment

```bash
# Deploy to dev
export TELEGRAM_BOT_TOKEN=your_token
serverless deploy --stage dev

# Deploy to production
serverless deploy --stage production

# View function logs (live)
serverless logs -f telegramWebhook -t --stage dev

# Get deployment info
serverless info --stage dev

# Remove deployment completely
serverless remove --stage dev
```

### Webhook Management (Manual)

```bash
# Check webhook status
TELEGRAM_BOT_TOKEN=your_token python scripts/set_webhook.py info

# Delete webhook (to switch back to polling)
TELEGRAM_BOT_TOKEN=your_token python scripts/set_webhook.py delete

# Manually set webhook
WEBHOOK_URL=https://your-url/webhook \
TELEGRAM_BOT_TOKEN=your_token \
python scripts/set_webhook.py
```

---

## 🔄 Switching Between Modes

### From Local → AWS (Deploy)

1. Stop local bot (Ctrl+C)
2. Deploy: `serverless deploy --stage dev`
3. Webhook is set automatically!

### From AWS → Local (Development)

1. Delete webhook:
   ```bash
   TELEGRAM_BOT_TOKEN=your_token python scripts/set_webhook.py delete
   ```
2. Start local:
   ```bash
   poetry run python -m src.bot.run_polling
   ```

**⚠️ Important:** Only ONE mode can be active at a time!

---

## 🏗️ Architecture

### Conversation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER STARTS BOT                          │
│                           /start                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        MAIN MENU                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐               │
│  │ ➕ Add new search   │  │ 📋 View searches    │               │
│  └─────────────────────┘  └─────────────────────┘               │
└─────────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌──────────────────────┐    ┌──────────────────────────────────────┐
│   ADD SEARCH FLOW    │    │         VIEW SEARCHES                │
│                      │    │                                      │
│  "Send me the link"  │    │  Your current searches:              │
│         │            │    │  ┌────────────────────────────────┐  │
│         ▼            │    │  │ ❌ Tel Aviv 3 rooms            │  │
│  User sends URL      │    │  │ ❌ Jerusalem apartment         │  │
│         │            │    │  │ ❌ Haifa near beach            │  │
│         ▼            │    │  └────────────────────────────────┘  │
│  "Name this search?" │    │  ┌────────────────────────────────┐  │
│         │            │    │  │ ⬅️ Back to menu                │  │
│         ▼            │    │  └────────────────────────────────┘  │
│  User sends name     │    │                                      │
│         │            │    │  Click ❌ to delete a search         │
│         ▼            │    └──────────────────────────────────────┘
│  ✅ Search added!    │
│  [Back to Main Menu] │
└──────────────────────┘
```

### Local Mode (Polling)
```
┌──────────┐     Long Polling      ┌──────────────┐
│ Telegram │ ◄──────────────────► │  Your Local  │
│  Server  │                       │   Machine    │
└──────────┘                       └──────────────┘
```

### AWS Mode (Webhook)
```
┌──────────┐      Webhook POST     ┌─────────────┐     ┌──────────┐
│ Telegram │ ──────────────────► │ API Gateway │ ──► │  Lambda  │
│  Server  │                       │             │     │ Function │
└──────────┘                       └─────────────┘     └────┬─────┘
                                                            │
                                                            ▼
                                                     ┌──────────┐
                                                     │ DynamoDB │
                                                     └──────────┘
```

---

## 🕵️ Scanner Architecture & Anti-Bot (CloakBrowser)

### The problem
Yad2's bot protection (Radware/ShieldSquare) blocks plain HTTP requests coming
from AWS IP ranges. Testing showed all AWS regions are blocked at the IP level,
so region migration is not a viable fix. The protection is **fingerprint-based**,
not purely IP-based — a real stealth browser passes the challenge even from an
AWS Lambda IP (no residential proxy required).

The solution is [CloakBrowser](https://cloakbrowser.dev) — a patched, stealth
Chromium (Playwright drop-in). Because Chromium + its libraries far exceed
Lambda's 250 MB zip limit, only the search worker runs as a container-image
Lambda (up to 10 GB, pulled from ECR). Everything else (webhook, orchestrator)
stays a normal zip Lambda.

### Orchestrator to Worker (container) flow
```
        every 30 min (cron, 6 AM-midnight Israel)
                          |
                          v
        +----------------------------------+
        |  searchOrchestrator  (zip Lambda)|
        |  - reads all searches from DDB   |
        |  - splits into budget batches    |
        |    (<= MAX_REQUESTS_PER_WORKER)  |
        |  - invokes workers synchronously |
        |  - aggregates + sends 1 summary  |
        +---------------+------------------+
                        |  invoke (RequestResponse), per batch
                        v
        +----------------------------------+
        | searchWorkerImg (CONTAINER Lambda)|
        |  - CloakBrowser + baked Chromium |
        |  - fetches each search page      |
        |  - parses __NEXT_DATA__ listings |
        |  - detects new items (ID bank)   |
        |  - optional: notify user         |
        +---------------+------------------+
                        |
              +---------+---------+
              v                   v
        +-----------+       +-----------+
        | Yad2.co.il|       | DynamoDB  |
        | (stealth) |       | searches  |
        +-----------+       |  + stats  |
                            +-----------+
```

### How the browser fetch works
- [`src/yad2/browser_fetcher.py`](src/yad2/browser_fetcher.py) wraps CloakBrowser
  behind a simple `fetch_html(url)`. The scanner runs inside an asyncio loop, but
  Playwright's sync API cannot run on a running event loop, so all browser work
  runs on a single dedicated background thread that owns the browser instance.
  `fetch_html` dispatches to that thread and blocks for the result.
- [`src/yad2/parser.py`](src/yad2/parser.py) routes page fetches through the
  browser when `USE_CLOAKBROWSER=1`, otherwise falls back to plain HTTP. It also
  fails fast on an empty/missing search URL (guards against orphaned records).

### Container image build (Dockerfile.worker)
- Base: `public.ecr.aws/lambda/python:3.12`
- Installs Chromium's system libraries + `cloakbrowser`
- Bakes Chromium at build time and sets `CLOAKBROWSER_BINARY_PATH` so the runtime
  never re-downloads it (Lambda's `/tmp` would run out of space).
- Points all cache/config dirs (`HOME`, `XDG_*`) at `/tmp` (only writable path).

### Deploying the worker image (manual build + push)
Serverless-managed image builds stall behind corporate proxies, so the worker
image is built and pushed manually, then referenced via `WORKER_IMAGE_URI`.

Run the build/push with the corporate VPN/proxy OFF — the proxy's TLS
interception breaks `dnf` and ECR pushes.

```bash
# 1) Build + push the worker image (VPN OFF)
./build_worker_image.sh   # builds & pushes to the yad2-worker ECR repo
# (uses docker build --platform linux/amd64 --provenance=false --output type=docker
#  -f Dockerfile.worker ; the provenance/output flags avoid an OCI/attestation
#  manifest that Lambda rejects)

# 2) Deploy the stack referencing the pre-built image (VPN can be ON)
WORKER_IMAGE_URI=<acct>.dkr.ecr.<region>.amazonaws.com/yad2-worker:latest \
TELEGRAM_BOT_TOKEN=... ADMIN_CHAT_ID=... ADMIN_BOT_TOKEN=... \
npx serverless deploy --stage prod --region eu-west-2
```

The worker is defined in [`serverless.yml`](serverless.yml) as `searchWorkerImg`
with `image: ${env:WORKER_IMAGE_URI}`, `memorySize: 2048`, `timeout: 300`, and
`ephemeralStorageSize: 2048`. The orchestrator timeout is `600` so all batches
finish (container cold starts are ~20-28s each).

Zip to image note: switching a custom-named function from zip to image forces a
CloudFormation replacement it cannot do in-place. The worker was therefore given
a new logical key (`searchWorkerImg`) so CloudFormation creates it fresh; the
orchestrator's `WORKER_FUNCTION_NAME` and the IAM invoke ARN reference the same
new name.

### Relevant environment variables
| Var | Where | Purpose |
|-----|-------|---------|
| `USE_CLOAKBROWSER` | worker image | `1` enables the stealth-browser fetch path |
| `CLOAKBROWSER_BINARY_PATH` | worker image | Points to the baked Chromium (skips runtime download) |
| `WORKER_IMAGE_URI` | deploy env | ECR image URI the worker Lambda runs |
| `WORKER_FUNCTION_NAME` | orchestrator | Name of the worker Lambda to invoke |
| `MAX_REQUESTS_PER_WORKER` | orchestrator | Batch budget so each worker stays under Yad2 limits |
| `CLOAK_PROXY` | worker (optional) | Residential proxy, if ever needed — not required for AWS |

---

## 📁 Project Structure

```
yad2-notification-bot/
├── src/
│   ├── config.py              # Settings from environment
│   ├── api/
│   │   ├── main.py            # FastAPI app
│   │   ├── webhook.py         # Telegram webhook handler
│   │   └── lambda_entry.py    # AWS Lambda entry point
│   ├── bot/
│   │   ├── bot_instance.py    # Bot & Dispatcher
│   │   ├── router.py          # Main router
│   │   ├── states.py          # FSM states
│   │   ├── run_polling.py     # Local dev entry point
│   │   ├── handlers/          # Message handlers
│   │   ├── keyboards/         # Inline keyboards
│   │   └── db/                # DynamoDB data layer
│   ├── scanner/              # Search-scanning pipeline
│   │   ├── orchestrator.py    # Cron entry: batches + invokes workers, sends summary
│   │   ├── worker.py          # Worker Lambda handler (runs in container image)
│   │   ├── scanner.py         # Core scan logic (new-item detection)
│   │   ├── notifier.py        # Telegram notifications
│   │   └── stats.py           # Per-run stats + alerts
│   └── yad2/                 # Yad2 access layer
│       ├── parser.py          # Page fetch + __NEXT_DATA__ parsing
│       └── browser_fetcher.py # CloakBrowser (stealth Chromium) fetcher
├── scripts/
│   ├── set_webhook.py         # Webhook management
│   ├── worker_test_payload.json      # Sample worker invoke payload
│   └── worker_test_nonotif.json      # Worker test payload (no notifications)
├── Dockerfile.worker          # Container image for the CloakBrowser worker
├── build_worker_image.sh      # Build + push the worker image to ECR
├── serverless.yml             # AWS deployment config (mixed zip + container)
├── package.json               # Node.js dependencies
├── pyproject.toml             # Python dependencies
├── .env                       # Environment variables (git ignored)
└── .env.example               # Example environment file
```

---

## 🔧 Troubleshooting

### Bot doesn't respond after deployment

1. Check webhook is set:
   ```bash
   TELEGRAM_BOT_TOKEN=your_token python scripts/set_webhook.py info
   ```

2. Check Lambda logs:
   ```bash
   serverless logs -f telegramWebhook -t --stage dev
   ```

### Deployment fails with permission error

Add the IAM policy from `docs/aws-iam-policy.json` to your AWS user.

### Bot works locally but not on AWS

Make sure you deleted the webhook before running locally:
```bash
TELEGRAM_BOT_TOKEN=your_token python scripts/set_webhook.py delete
```

---

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `AWS_REGION` | AWS region | Yes (default: eu-central-1) |

---

## 📝 TODO

- [ ] Implement DynamoDB database layer
- [ ] Add Yad2 scraper/scanner
- [ ] Implement notification sender
- [ ] Add search scanner Lambda function (cron job)

---

## 📄 License

MIT
