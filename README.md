# comments_analyzer

> **WARNING:** This repository may be unstable or non-functional. Use at your own risk.

A tool for analyzing toxicity and hate speech in comments from Telegram and YouTube channels.

## Analysis Modes

### 1. Keyword-based (no LLM required)

`HateSpeechDetector` — fast, offline, no external dependencies. Scans comments using regex patterns across 4 categories:

- `death_wishes` — explicit death threats
- `ethnic_slurs` — ethnic slurs and derogatory terms
- `dehumanization` — dehumanizing language
- `violence_calls` — calls for violence

```bash
python main.py --tg @channel --no-analysis   # collect only
python main.py --tg @channel --basic-stats   # keyword stats, no LLM
```

### 2. LLM-based (via LM Studio)

`ToxicityAnalyzer` — classifies comments as `toxic`, `neutral`, or `friendly` using a local LLM. Requires [LM Studio](https://lmstudio.ai/) running locally.

`PoliticalAnalyzer` — classifies political alignment of comments.

```bash
python main.py --tg @channel     # full analysis with LLM
python main.py --yt @channel     # YouTube + LLM
```

## Sources

| | Telegram | YouTube |
|---|---|---|
| Flag | `--tg @channelname` | `--yt @handle` or `--yt UC...` |
| Recommended limit | 100 posts | 50 videos |
| Main constraint | Ban risk | API quota (10k/day) |
| Incremental window | 7 days | 30 days |
| Data directory | `data/telegram/` | `data/youtube/` |

## Features

- Incremental updates — only new comments are fetched and analyzed
- Resume / checkpoint — interrupt and continue analysis at any point
- Parallel processing of multiple channels
- Results saved as JSON

## Quick Start

```bash
pip install -r requirements.txt
cp env_example.txt .env   # fill in your credentials
```

See [docs/CONFIG.md](docs/CONFIG.md) for full configuration reference.

### Telegram

Get API credentials at https://my.telegram.org/apps, add to `.env`:

```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+yournumber
```

### YouTube

Get an API key at https://console.cloud.google.com (enable YouTube Data API v3), add to `.env`:

```env
YOUTUBE_API_KEY=your_key
```

### LM Studio (for LLM analysis)

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Load a model
3. Start Local Server
4. Set in `.env`: `LM_STUDIO_API_URL=http://localhost:1234/v1/chat/completions`

## Usage

```bash
# Telegram — collect and analyze (100 posts)
python main.py --tg @channel

# Telegram — specific post count
python main.py --tg @channel 50

# YouTube — collect and analyze (50 videos)
python main.py --yt @channel

# Collect only, no LLM
python main.py --tg @channel --no-analysis

# Keyword-based stats only (no LLM, no API calls)
python main.py --tg @channel --basic-stats

# Work with already downloaded data
python main.py --tg @channel --stats-only

# Force re-analyze all comments
python main.py --tg @channel --force-reanalysis

# YouTube: analyze only replies (often more toxic)
python main.py --yt @channel --stats-only --only-replies

# YouTube: analyze only top-level comments
python main.py --yt @channel --stats-only --only-top
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for all flags.

## Configuration (.env)

```env
# Telegram
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_REQUEST_DELAY=0.5
DEFAULT_POSTS_LIMIT=100

# YouTube
YOUTUBE_API_KEY=
DEFAULT_VIDEOS_LIMIT=50

# LM Studio
LM_STUDIO_API_URL=http://localhost:1234/v1/chat/completions
BATCH_SIZE=5
```

## Data Structure

```
data/
├── telegram/
│   └── channelname/
│       ├── posts/
│       ├── analysis/
│       └── channel_info.json
└── youtube/
    └── channelname/
        ├── posts/
        ├── analysis/
        └── channel_info.json
```

## Project Structure

```
comments_analyzer/
├── main.py
├── requirements.txt
├── env_example.txt
├── src/
│   ├── collectors.py           # base collector classes
│   ├── youtube_collector.py    # YouTube data collection
│   ├── stats_analyzer.py       # statistics
│   ├── toxicity_analyzer.py    # LLM-based toxicity (toxic/neutral/friendly)
│   ├── hate_speech_detector.py # keyword-based hate speech (no LLM)
│   └── political_analyzer.py   # LLM-based political alignment
└── docs/
    ├── ARCHITECTURE.md
    ├── CHANGELOG.md
    ├── CONFIG.md
    ├── EXAMPLES.md
    ├── QUICKSTART.md
    └── TROUBLESHOOTING.md
```

## Rate Limits and Safety

**Telegram:** Do not fetch more than 100-200 posts per run. Use `TELEGRAM_REQUEST_DELAY=0.5`. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

**YouTube:** API quota is 10,000 units/day. 50 videos with comments costs ~150 units. Use `--stats-only` to work with cached data.

## Language Support

**Keyword-based analysis (hate speech) supports Russian and Ukrainian only.** The patterns in `HateSpeechDetector` are written in Russian and Ukrainian and will only match comments in those languages. LLM-based toxicity and political analysis sends English prompts and works with any language the loaded model supports.

## Recommended LLM Models

For use with LM Studio:
- Saiga / Vikhr (good Russian-language models)
- LLaMA 3 with Russian fine-tune

## License

See `LICENSE`.
