# Examples

## Basic Usage

```bash
# Analyze last 100 posts from a Telegram channel
python main.py --tg @durov 100

# Analyze last 50 YouTube videos
python main.py --yt @MrBeast 50

# YouTube by channel ID
python main.py --yt UC1234567890abcdef 30
```

## Keyword-based Analysis (no LLM)

```bash
# Fast hate speech detection, no LLM required
python main.py --tg @channel --basic-stats

# Same for YouTube
python main.py --yt @channel --basic-stats
```

## Collect First, Analyze Later

```bash
# Step 1: collect only
python main.py --tg @channel --no-analysis

# Step 2: analyze cached data (no network needed)
python main.py --tg @channel --stats-only
```

## Resume Interrupted Analysis

```bash
# Just re-run the same command — it continues from where it stopped
python main.py --tg @channel 200
```

## Re-analyze with a Different Model

```bash
# Switch model in LM Studio, then:
python main.py --tg @channel --force-reanalysis
```

## YouTube Comment Types

```bash
# Replies tend to be more toxic — analyze separately
python main.py --yt @channel --stats-only --only-replies

# Top-level comments only
python main.py --yt @channel --stats-only --only-top
```

## Parallel Channels

```bash
# Run multiple channels simultaneously (separate terminals or background)
python main.py --tg @channel1 &
python main.py --tg @channel2 &
python main.py --yt @ytchannel &
```

## Working Offline (no API quota)

```bash
# After initial data collection, all of these work without any network calls:
python main.py --tg @channel --stats-only
python main.py --tg @channel --basic-stats
python main.py --yt @channel --stats-only
```
