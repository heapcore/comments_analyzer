# Architecture

## Overview

```
main.py
  |
  |-- TelegramCollector (src/collectors.py)
  |     |-- fetches posts and comments via Telethon
  |     |-- saves to data/telegram/<channel>/
  |
  |-- YouTubeCollector (src/youtube_collector.py)
  |     |-- fetches videos and comments via YouTube Data API v3
  |     |-- saves to data/youtube/<channel>/
  |
  |-- StatsAnalyzer (src/stats_analyzer.py)
  |     |-- counts unique users, top-100 active, comment frequency
  |
  |-- HateSpeechDetector (src/hate_speech_detector.py)   [no LLM]
  |     |-- regex-based keyword matching
  |     |-- categories: death_wishes, ethnic_slurs, dehumanization, violence_calls
  |
  |-- ToxicityAnalyzer (src/toxicity_analyzer.py)        [LLM]
  |     |-- classifies comments as toxic / neutral / friendly
  |     |-- sends batches to LM Studio local API
  |
  |-- PoliticalAnalyzer (src/political_analyzer.py)      [LLM]
        |-- classifies political alignment of comments
```

## Data Flow

1. **Collect** — fetch posts/videos and their comments, save as JSON files in `data/`
2. **Analyze** — run detectors/analyzers over cached JSON data
3. **Output** — print statistics to console, save analysis results to `data/<source>/<channel>/analysis/`

## Incremental Updates

On each run the tool checks which posts/videos are within the update window:
- Telegram: posts newer than 7 days
- YouTube: videos newer than 30 days

Only new comments are fetched. Previously analyzed comments are skipped unless `--force-reanalysis` is passed.

## Resume / Checkpoint

Analysis results are written per-post/per-video as they complete. If a run is interrupted, re-running the same command automatically skips already-analyzed content.

## LLM Integration

`ToxicityAnalyzer` and `PoliticalAnalyzer` communicate with LM Studio via its OpenAI-compatible REST API. Comments are sent in batches (`BATCH_SIZE`). Failed batches are retried once before falling back to `neutral`.

## Keyword-based Analysis (no LLM)

`HateSpeechDetector` uses compiled regex patterns with prefix matching (e.g., `орк` matches `орков`, `оркам`). No external dependencies, fully offline, instant results.
