"""
Comments Toxicity Analyzer
Incremental comment analyzer for Telegram and YouTube channels
"""

import asyncio
import os
import argparse
import getpass
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from datetime import datetime, timedelta, timezone
import json

from src.collectors import ChannelDataManager
from src.youtube_collector import YoutubeCommentsCollector

# Load environment variables
load_dotenv()

# Telegram API configuration
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")
TELEGRAM_PASSWORD_2FA = os.getenv("TELEGRAM_PASSWORD_2FA")
TELEGRAM_SESSION_NAME = "telegram_analyzer"
TELEGRAM_REQUEST_DELAY = float(os.getenv("TELEGRAM_REQUEST_DELAY", "0.5"))
MAX_POST_AGE_DAYS = 7  # Telegram

# YouTube API configuration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
MAX_VIDEO_AGE_DAYS = 30  # YouTube

# Base data directory
DATA_DIR = Path("data")


class TelegramCommentsCollector:
    """Collects comments from Telegram channels."""

    def __init__(self, api_id, api_hash, phone, session_name="telegram_analyzer"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client = None

    async def connect(self):
        """Connect to Telegram."""
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

            if TELEGRAM_PASSWORD_2FA:
                await self.client.start(
                    phone=self.phone, password=TELEGRAM_PASSWORD_2FA
                )
            else:
                await self.client.start(
                    phone=self.phone,
                    password=lambda: getpass.getpass("Enter 2FA password (hidden): "),
                )
            print("✓ Connected to Telegram")
        except Exception as e:
            error_msg = str(e)
            if "key is not registered" in error_msg.lower():
                print("\n! Error: session is corrupted or expired")
                print(f"  Fix: delete {self.session_name}.session* and restart")
                raise
            else:
                raise

    async def get_channel_posts(self, channel_username, limit=100):
        """Fetch the latest posts from a channel."""
        try:
            channel = await self.client.get_entity(channel_username)
            posts = []

            async for message in self.client.iter_messages(channel, limit=limit):
                posts.append(
                    {
                        "id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text
                        or message.message
                        or "[Media without text]",
                        "views": message.views,
                        "forwards": message.forwards,
                        "replies": getattr(message.replies, "replies", 0)
                        if message.replies
                        else 0,
                    }
                )

            print(f"✓ Fetched {len(posts)} posts from {channel_username}")
            return posts

        except Exception as e:
            print(f"✗ Error fetching posts: {e}")
            return []

    async def get_post_comments(
        self, channel_username, post_id, existing_comment_ids=None
    ):
        """Fetch comments for a post."""
        if existing_comment_ids is None:
            existing_comment_ids = set()

        try:
            channel = await self.client.get_entity(channel_username)
            comments = []
            new_count = 0

            async for message in self.client.iter_messages(channel, reply_to=post_id):
                if message.id in existing_comment_ids:
                    continue

                if message.text or message.message:
                    user_info = {
                        "id": message.sender_id,
                        "username": None,
                        "first_name": None,
                        "last_name": None,
                    }

                    try:
                        sender = await message.get_sender()
                        if sender:
                            user_info["username"] = getattr(sender, "username", None)
                            user_info["first_name"] = getattr(
                                sender, "first_name", None
                            )
                            user_info["last_name"] = getattr(sender, "last_name", None)
                    except:
                        pass

                    comments.append(
                        {
                            "comment_id": message.id,
                            "post_id": post_id,
                            "comment_type": "top_level",  # Telegram has no nested replies
                            "user": user_info,
                            "text": message.text or message.message,
                            "date": message.date.isoformat(),
                        }
                    )
                    new_count += 1

            if new_count > 0:
                print(f"  └─ Fetched {new_count} new comments")

            return comments

        except Exception as e:
            error_msg = str(e)
            if "key is not registered" in error_msg.lower():
                print("  └─ ! Session error — reconnect required")
                print(
                    f"  └─ Tip: delete telegram_session_{channel_username.replace('@', '')}.session and restart"
                )
            else:
                print(f"  └─ ✗ Error: {e}")
            return []

    async def sync_channel_data(
        self, channel_username, data_manager: ChannelDataManager, posts_limit=100
    ):
        """Sync channel data with incremental updates."""
        await self.connect()

        print("\nPhase 1: Fetching data from Telegram")
        print("=" * 60)

        print(f"Fetching latest {posts_limit} posts...")
        posts = await self.get_channel_posts(channel_username, posts_limit)

        if not posts:
            print("✗ No posts found")
            return None

        stats = {
            "total_posts": len(posts),
            "new_posts": 0,
            "updated_posts": 0,
            "skipped_posts": 0,
            "total_comments": 0,
            "new_comments": 0,
        }

        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=MAX_POST_AGE_DAYS)

        print(
            f"\nProcessing posts (updating only posts newer than {MAX_POST_AGE_DAYS} days):\n"
        )

        for i, post in enumerate(posts, 1):
            post_id = post["id"]
            post_date = datetime.fromisoformat(post["date"])
            post_age_days = (now - post_date).days

            print(
                f"[{i}/{len(posts)}] Post {post_id} ({post_age_days}d ago)...", end=" "
            )

            replies_count = post.get("replies", 0)

            if data_manager.post_exists(str(post_id)):
                if post_date < cutoff_date:
                    print("Skipped (older than 7 days)")
                    stats["skipped_posts"] += 1
                else:
                    if replies_count == 0 and not data_manager.load_comments(
                        str(post_id)
                    ):
                        print("Comments unavailable")
                        stats["skipped_posts"] += 1
                    else:
                        print("Updating comments...")
                        existing_comments = data_manager.load_comments(str(post_id))
                        existing_ids = {c["comment_id"] for c in existing_comments}

                        new_comments = await self.get_post_comments(
                            channel_username, post_id, existing_ids
                        )

                        if new_comments:
                            all_comments = existing_comments + new_comments
                            data_manager.save_post_data(
                                str(post_id), post, all_comments
                            )
                            stats["new_comments"] += len(new_comments)
                            stats["total_comments"] += len(all_comments)
                            stats["updated_posts"] += 1
                        else:
                            stats["total_comments"] += len(existing_comments)
                            stats["skipped_posts"] += 1
            else:
                if replies_count == 0:
                    print("Comments unavailable")
                    data_manager.save_post_data(str(post_id), post, [])
                    stats["skipped_posts"] += 1
                else:
                    print("New post, downloading...")
                    comments = await self.get_post_comments(channel_username, post_id)
                    data_manager.save_post_data(str(post_id), post, comments)
                    stats["new_posts"] += 1
                    stats["new_comments"] += len(comments)
                    stats["total_comments"] += len(comments)

            await asyncio.sleep(TELEGRAM_REQUEST_DELAY)

        channel_info = {
            "channel": channel_username,
            "last_sync": now.isoformat(),
            "posts_limit": posts_limit,
            "stats": stats,
        }
        data_manager.save_channel_info(channel_info)

        print(f"\n{'=' * 60}")
        print("Sync statistics:")
        print(f"  • Posts checked:    {stats['total_posts']}")
        print(f"  • New posts:        {stats['new_posts']}")
        print(f"  • Updated posts:    {stats['updated_posts']}")
        print(f"  • Skipped (old):    {stats['skipped_posts']}")
        print(f"  • Total comments:   {stats['total_comments']}")
        print(f"  • New comments:     {stats['new_comments']}")

        return stats

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()
            print("✓ Disconnected from Telegram")


async def main():
    """Main entry point."""
    default_posts_tg = int(os.getenv("DEFAULT_POSTS_LIMIT", "100"))
    default_videos_yt = int(os.getenv("DEFAULT_VIDEOS_LIMIT", "50"))

    parser = argparse.ArgumentParser(
        description="Comments analyzer for Telegram and YouTube channels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:

TELEGRAM:
  python main.py --tg @channelname                    # Analyze {default_posts_tg} posts
  python main.py --tg @durov 50                       # Analyze 50 posts
  python main.py --tg channel --no-analysis           # Sync only
  python main.py --tg channel --basic-stats           # Quick stats

YOUTUBE:
  python main.py --yt @MrBeast                        # Analyze {default_videos_yt} videos
  python main.py --yt UC1234567890abcdef 30           # Analyze 30 videos
  python main.py --yt channel --no-analysis           # Sync only
  python main.py --yt channel --basic-stats           # Quick stats
  python main.py --yt channel --stats-only --min-likes 1000  # Comments with 1000+ likes

COMMON FLAGS:
  --stats-only            # Analyze local data without fetching new
  --force-reanalysis      # Re-analyze ALL comments from scratch
  --min-likes N           # Filter: comments with at least N likes

NOTE: hate_comments.json is always created in data/.../analysis/
        """,
    )

    # Mutually exclusive group for source selection
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--tg", "--telegram", action="store_true", help="Use Telegram as the source"
    )
    source_group.add_argument(
        "--yt", "--youtube", action="store_true", help="Use YouTube as the source"
    )

    parser.add_argument(
        "channel", type=str, help="Channel username (@channelname) or Channel ID"
    )

    parser.add_argument(
        "limit",
        type=int,
        nargs="?",
        help=f"Number of posts/videos (default: {default_posts_tg} for TG, {default_videos_yt} for YT)",
    )

    parser.add_argument(
        "--no-analysis", action="store_true", help="Sync data only, skip LLM analysis"
    )

    parser.add_argument(
        "--force-reanalysis",
        action="store_true",
        help="Force re-analysis of ALL comments",
    )

    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Run on already-downloaded local data only",
    )

    parser.add_argument(
        "--basic-stats", action="store_true", help="Quick stats only (no API, no LLM)"
    )

    parser.add_argument(
        "--only-replies",
        action="store_true",
        help="Analyze reply comments only (YouTube)",
    )

    parser.add_argument(
        "--only-top",
        action="store_true",
        help="Analyze top-level comments only, no replies (YouTube)",
    )

    parser.add_argument(
        "--min-likes",
        type=int,
        default=None,
        help="Filter: only comments with at least N likes (e.g. --min-likes 1000)",
    )

    parser.add_argument(
        "--export-hate-speech",
        type=str,
        default=None,
        metavar="FILE",
        help="Additional hate speech export path (always saved to analysis/hate_comments.json by default)",
    )

    args = parser.parse_args()

    if args.basic_stats:
        args.stats_only = True
        args.no_analysis = True

    # Determine source and parameters
    is_telegram = args.tg
    is_youtube = args.yt
    source = "telegram" if is_telegram else "youtube"
    source_name = "TELEGRAM" if is_telegram else "YOUTUBE"

    # Set default limit
    if args.limit is None:
        limit = default_posts_tg if is_telegram else default_videos_yt
    else:
        limit = args.limit

    channel = args.channel
    if is_telegram and not channel.startswith("@"):
        channel = f"@{channel}"

    print("=" * 60)
    print(f"{source_name} COMMENTS ANALYZER")
    print("=" * 60)
    print(f"Channel: {channel}")

    # Create data manager
    data_manager = ChannelDataManager(channel, source=source)
    print(f"✓ Data directory: {data_manager.base_dir}")

    # Stats-only mode
    if args.stats_only:
        if args.basic_stats:
            print(f"Mode: quick stats (no {source_name}, no LLM)")
        else:
            print(f"Mode: local data only (no {source_name} connection)")
        print("=" * 60 + "\n")

        all_post_ids = data_manager.get_all_post_ids()
        if not all_post_ids:
            print("✗ No saved data for this channel")
            print("  Run without --stats-only to fetch data first:")
            print(
                f"   python main.py --{'tg' if is_telegram else 'yt'} {channel} {limit}"
            )
            return

        entity_name = "posts" if is_telegram else "videos"
        print(f"✓ Found {len(all_post_ids)} {entity_name} with data")

        print("Loading all comments from local files...")
        all_comments = data_manager.load_all_comments()

        if not all_comments:
            print("✗ No comments in saved data")
            return

        print(f"✓ Loaded {len(all_comments)} comments\n")

        # Filter by comment type (YouTube only)
        if is_youtube and (args.only_replies or args.only_top):
            original_count = len(all_comments)
            if args.only_replies:
                all_comments = [
                    c for c in all_comments if c.get("comment_type") == "reply"
                ]
                print(
                    f"Filter: replies only — {len(all_comments)} of {original_count}\n"
                )
            elif args.only_top:
                all_comments = [
                    c for c in all_comments if c.get("comment_type") == "top_level"
                ]
                print(
                    f"Filter: top-level only — {len(all_comments)} of {original_count}\n"
                )

        # Filter by likes
        if args.min_likes is not None:
            original_count = len(all_comments)
            all_comments = [
                c for c in all_comments if c.get("likes", 0) >= args.min_likes
            ]
            print(
                f"Filter: {args.min_likes}+ likes — {len(all_comments)} of {original_count}\n"
            )

    else:
        # Normal mode: connect to API

        if is_telegram:
            # Check Telegram credentials
            if not TELEGRAM_API_ID or not TELEGRAM_API_HASH or not TELEGRAM_PHONE:
                print("✗ Error: Telegram environment variables not set")
                print("Create a .env file and set:")
                print("TELEGRAM_API_ID=your_api_id")
                print("TELEGRAM_API_HASH=your_api_hash")
                print("TELEGRAM_PHONE=your_phone_number")
                return

            print(f"Posts to check: {limit}")
            print(f"Updating only posts newer than {MAX_POST_AGE_DAYS} days")
            print("=" * 60 + "\n")

            channel_name = channel.replace("@", "")
            session_name = f"telegram_session_{channel_name}"

            collector = TelegramCommentsCollector(
                TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE, session_name
            )
        else:
            # Check YouTube credentials
            if not YOUTUBE_API_KEY:
                print("✗ Error: YOUTUBE_API_KEY not set")
                print("Create a .env file and set:")
                print("YOUTUBE_API_KEY=your_api_key")
                print("\nHow to get an API key:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a new project")
                print("3. Enable YouTube Data API v3")
                print("4. Create an API key under Credentials")
                return

            print(f"Videos to check: {limit}")
            print("=" * 60 + "\n")

            collector = YoutubeCommentsCollector(YOUTUBE_API_KEY)

        try:
            # PHASE 1: Sync data
            stats = await collector.sync_channel_data(channel, data_manager, limit)

            if not stats or stats["total_comments"] == 0:
                print("\n✗ No comments to analyze")
                return

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            return
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback

            traceback.print_exc()
            return
        finally:
            await collector.disconnect()

        print("\nLoading all comments from local files...")
        all_comments = data_manager.load_all_comments()
        entity_name = "posts" if is_telegram else "videos"
        print(
            f"✓ Loaded {len(all_comments)} comments from {len(data_manager.get_all_post_ids())} {entity_name}\n"
        )

        # Filter by comment type (YouTube only)
        if is_youtube and (args.only_replies or args.only_top):
            original_count = len(all_comments)
            if args.only_replies:
                all_comments = [
                    c for c in all_comments if c.get("comment_type") == "reply"
                ]
                print(
                    f"Filter: replies only — {len(all_comments)} of {original_count}\n"
                )
            elif args.only_top:
                all_comments = [
                    c for c in all_comments if c.get("comment_type") == "top_level"
                ]
                print(
                    f"Filter: top-level only — {len(all_comments)} of {original_count}\n"
                )

        # Filter by likes
        if args.min_likes is not None:
            original_count = len(all_comments)
            all_comments = [
                c for c in all_comments if c.get("likes", 0) >= args.min_likes
            ]
            print(
                f"Filter: {args.min_likes}+ likes — {len(all_comments)} of {original_count}\n"
            )

    # Common analysis section
    try:
        # PHASE 2: Basic statistics
        if not args.basic_stats:
            phase_number = 1 if args.stats_only else 2
            print(f"Phase {phase_number}: Basic statistics")
            print("=" * 60)

        from src.stats_analyzer import print_basic_statistics

        # Build hate speech export path (if specified)
        export_hate_file = None
        if args.export_hate_speech:
            if (
                args.export_hate_speech.startswith("/")
                or args.export_hate_speech[1:3] == ":\\"
            ):
                # Absolute path
                export_hate_file = args.export_hate_speech
            else:
                # Relative path — save inside analysis directory
                export_hate_file = str(
                    data_manager.analysis_dir / args.export_hate_speech
                )

        basic_stats = print_basic_statistics(
            all_comments, data_manager.analysis_dir, export_hate_file
        )

        # PHASE 3: LLM Analysis
        if not args.no_analysis:
            batch_size = int(os.getenv("BATCH_SIZE", "5"))

            phase_number = 2 if args.stats_only else 3
            print(
                f"\nPhase {phase_number}: Toxicity and political alignment analysis via LLM"
            )
            print("=" * 60)
            print(f"  Batch size: {batch_size} comments")
            print(
                f"  LM Studio API: {os.getenv('LM_STUDIO_API_URL', 'http://localhost:1234/...')}"
            )
            if args.force_reanalysis:
                print("  Mode: forced reanalysis (ALL comments)")
            else:
                print("  Resume: enabled (interrupt with Ctrl+C and continue later)")
            print("=" * 60 + "\n")

            estimated_requests = (len(all_comments) // batch_size + 1) * 2
            estimated_minutes = estimated_requests * 1.5 / 60
            print(
                f"Estimated time: {int(estimated_minutes)} minutes ({estimated_requests} requests)\n"
            )

            from src.stats_analyzer import analyze_comments_and_save

            results = analyze_comments_and_save(
                all_comments,
                save_dir=data_manager.analysis_dir,
                save_interval=100,
                force_reanalysis=args.force_reanalysis,
            )

            analysis_file = data_manager.analysis_dir / "latest_analysis.json"
            with open(analysis_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"\n✓ Analysis results saved: {analysis_file}")

            for temp_file in ["toxicity_temp.json", "political_temp.json"]:
                temp_path = data_manager.analysis_dir / temp_file
                if temp_path.exists():
                    temp_path.unlink()
        else:
            if args.basic_stats:
                print("\nBasic statistics complete.")
                print("To run LLM toxicity analysis:")
                print(
                    f"   python main.py --{'tg' if is_telegram else 'yt'} {channel} --stats-only"
                )
            else:
                print("\nLLM analysis skipped (--no-analysis)")
                print(
                    "Basic statistics saved above. Run without --no-analysis for toxicity analysis."
                )

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
