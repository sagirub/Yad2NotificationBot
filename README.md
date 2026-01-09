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

## 📁 Project Structure

```
yad2-notification-bot/
├── src/
│   ├── config.py              # Settings from environment
│   ├── api/
│   │   ├── main.py            # FastAPI app
│   │   ├── webhook.py         # Telegram webhook handler
│   │   └── lambda_entry.py    # AWS Lambda entry point
│   └── bot/
│       ├── bot_instance.py    # Bot & Dispatcher
│       ├── router.py          # Main router
│       ├── states.py          # FSM states
│       ├── run_polling.py     # Local dev entry point
│       ├── handlers/          # Message handlers
│       ├── keyboards/         # Inline keyboards
│       └── db/                # Database layer
├── scripts/
│   └── set_webhook.py         # Webhook management
├── docs/
│   └── aws-iam-policy.json    # Required AWS permissions
├── .github/workflows/
│   └── deploy.yml             # GitHub Actions CI/CD
├── serverless.yml             # AWS deployment config
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
