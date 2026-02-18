# Troubleshooting

## Telegram

**`The key is not registered in the system`**
- Check `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`

**`FloodWaitError: A wait of X seconds is required`**
- Increase `TELEGRAM_REQUEST_DELAY` in `.env`
- Reduce the number of posts per run

**Session error / authentication loop**
- Delete `telegram_session_*.session` file and re-run

**No comments returned**
- The channel may have comments disabled or restricted
- Try a different channel to verify your credentials work

## YouTube

**`quotaExceeded`**
- You have hit the 10,000 units/day limit
- Use `--stats-only` to work with cached data until quota resets (midnight Pacific Time)

**`channelNotFound`**
- Try using the channel ID (`UC...`) instead of `@handle`

**No videos returned**
- Check that the API key is valid and YouTube Data API v3 is enabled in Google Cloud Console

## LM Studio

**`ConnectionError: Cannot connect to LM Studio API`**
1. Open LM Studio
2. Load a model
3. Start Local Server (Developer tab)
4. Verify the URL in `.env` matches the server address

**Empty or garbled analysis results**
- The model may be too small for batch processing — reduce `BATCH_SIZE` to 1-3
- Try a different model

**Analysis is very slow**
- Reduce `BATCH_SIZE`
- Use a smaller/faster model
- Use `--basic-stats` for keyword-only analysis (instant, no LLM needed)

## General

**`ModuleNotFoundError`**
```bash
pip install -r requirements.txt
```

**Results seem incorrect**
- Use `--force-reanalysis` to reprocess all comments with current settings

## Avoiding Telegram Rate Limits

Telegram actively rate-limits accounts that make too many API requests too quickly.

**Warning signs:**
- `FloodWaitError: A wait of X seconds is required`
- Telegram asking for re-authentication unexpectedly
- Session becoming invalid

**Rules:**
- Do not fetch more than 100-200 posts per run
- Always use a delay between requests: `TELEGRAM_REQUEST_DELAY=0.5` or higher
- Do not run multiple Telegram instances with the same account simultaneously
- Do not run on a fresh account — use one with normal activity history

**If you get banned:**
1. Stop all requests immediately
2. Wait 24 hours before retrying
3. Increase `TELEGRAM_REQUEST_DELAY`
4. Reduce `DEFAULT_POSTS_LIMIT`

**Safe defaults:**
```env
TELEGRAM_REQUEST_DELAY=0.5
DEFAULT_POSTS_LIMIT=100
```
