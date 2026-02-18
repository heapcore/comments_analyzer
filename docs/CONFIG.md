# Configuration

All settings are stored in `.env`. Copy `env_example.txt` to `.env` and fill in your values.

## Full .env Reference

```env
# --- Telegram ---
TELEGRAM_API_ID=           # from https://my.telegram.org/apps
TELEGRAM_API_HASH=         # from https://my.telegram.org/apps
TELEGRAM_PHONE=            # your phone number with country code, e.g. +79001234567
TELEGRAM_REQUEST_DELAY=0.5 # delay between requests in seconds (increase if getting banned)
DEFAULT_POSTS_LIMIT=100    # default number of posts to fetch

# --- YouTube ---
YOUTUBE_API_KEY=           # from https://console.cloud.google.com
DEFAULT_VIDEOS_LIMIT=50    # default number of videos to fetch

# --- LM Studio ---
LM_STUDIO_API_URL=http://localhost:1234/v1/chat/completions
BATCH_SIZE=5               # comments per LLM request
```

## Getting API Credentials

### Telegram

1. Go to https://my.telegram.org/apps
2. Create an application
3. Copy `api_id` and `api_hash` to `.env`
4. On first run you will be asked to enter the verification code sent to your phone

### YouTube

1. Go to https://console.cloud.google.com
2. Create a project
3. Enable **YouTube Data API v3**
4. Create an API key under Credentials
5. Copy the key to `.env`

YouTube API quota: **10,000 units/day**. Fetching 50 videos with comments costs ~150 units.

### LM Studio

1. Download from https://lmstudio.ai/
2. Load a model (recommended: Saiga, Vikhr, or LLaMA 3 with Russian fine-tune)
3. Start Local Server (default port 1234)
4. The default URL in `.env` should work as-is

## Notes

- LLM analysis is optional. Use `--basic-stats` or `--no-analysis` to skip it entirely.
- Increase `TELEGRAM_REQUEST_DELAY` if you get `FloodWaitError`. See [AVOIDING_BAN.md](AVOIDING_BAN.md).
- Use `--stats-only` when YouTube API quota is exhausted to keep working with cached data.
