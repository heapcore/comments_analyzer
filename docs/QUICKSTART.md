# Quick Start and Commands Reference

## Setup

1. Clone the repo and install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `env_example.txt` to `.env` and fill in your credentials. See [CONFIG.md](CONFIG.md) for details.

3. Start LM Studio, load a model, and enable the Local Server.

## Basic Syntax

```bash
python main.py --tg @channel [limit] [flags]
python main.py --yt @channel [limit] [flags]
```

One of `--tg` / `--yt` is required.

## Flags

| Flag | Description |
|------|-------------|
| `--tg`, `--telegram` | Use Telegram source |
| `--yt`, `--youtube` | Use YouTube source |
| `--no-analysis` | Collect comments only, skip LLM analysis |
| `--stats-only` | Run on locally cached data, no new fetching |
| `--basic-stats` | Keyword-based stats only (no API calls, no LLM) |
| `--force-reanalysis` | Re-analyze all comments from scratch |
| `--only-replies` | YouTube: analyze replies only |
| `--only-top` | YouTube: analyze top-level comments only |
| `--min-likes N` | Filter: only comments with at least N likes |
| `--export-hate-speech FILE` | Additional hate speech export path |

## Examples

```bash
# Collect and analyze 100 Telegram posts
python main.py --tg @channel 100

# Collect only, skip LLM
python main.py --tg @channel --no-analysis

# Keyword-based hate speech stats (fully offline)
python main.py --tg @channel --basic-stats

# Work with cached data (no network)
python main.py --tg @channel --stats-only

# Re-analyze with a new LLM model
python main.py --tg @channel --force-reanalysis

# Resume interrupted analysis (automatic — just re-run the same command)
python main.py --tg @channel

# Run multiple channels in parallel
python main.py --tg @channel1 &
python main.py --tg @channel2 &

# YouTube: compare replies vs top-level toxicity
python main.py --yt @channel --stats-only --only-replies
python main.py --yt @channel --stats-only --only-top

# YouTube: analyze only highly-liked comments
python main.py --yt @channel --stats-only --min-likes 1000
```

## Channel ID Formats

**Telegram:** `@channelname` or numeric ID

**YouTube:** `@handle` or `UC...` channel ID

```bash
python main.py --yt @MrBeast 30
python main.py --yt UC1234567890abcdef 100
```

## Batch Size

Controls how many comments are sent to the LLM per request. Set in `.env`:

```env
BATCH_SIZE=5
```

Larger batches are faster but may reduce accuracy on smaller models. Recommended range: 3-10.
