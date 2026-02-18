"""
YouTube comment collector using YouTube Data API v3.
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.collectors import CommentsCollector, ChannelDataManager

# Max age of a video to still update its comments
MAX_VIDEO_AGE_DAYS = 365


class YoutubeCommentsCollector(CommentsCollector):
    """Collects comments from YouTube channels via YouTube Data API v3."""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: YouTube Data API key
        """
        self.api_key = api_key
        self.youtube = None

    async def connect(self):
        """Initialize YouTube API client."""
        try:
            self.youtube = build("youtube", "v3", developerKey=self.api_key)
            print("✓ Connected to YouTube API")
        except Exception as e:
            print(f"✗ Failed to connect to YouTube API: {e}")
            raise

    async def disconnect(self):
        """Release YouTube API client (no explicit disconnect needed)."""
        self.youtube = None
        print("✓ Disconnected from YouTube API")

    def _get_channel_id_by_handle(self, channel_handle: str) -> Optional[str]:
        """
        Resolve a channel @handle or custom URL to a channel ID.

        Args:
            channel_handle: handle (e.g. @channelname or channelname)

        Returns:
            channel_id or None
        """
        try:
            handle = channel_handle.lstrip("@")

            request = self.youtube.search().list(
                part="snippet", q=handle, type="channel", maxResults=5
            )
            response = request.execute()

            if response["items"]:
                # Prefer exact match
                for item in response["items"]:
                    custom_url = item["snippet"].get("customUrl", "").lstrip("@")
                    title = item["snippet"]["title"]

                    if (
                        custom_url.lower() == handle.lower()
                        or title.lower() == handle.lower()
                    ):
                        return item["snippet"]["channelId"]

                # Fall back to first result
                return response["items"][0]["snippet"]["channelId"]

            return None

        except HttpError as e:
            print(f"✗ Channel search error: {e}")
            return None

    async def get_posts(self, channel_id: str, limit: int = 50) -> List[Dict]:
        """
        Fetch the latest videos from a channel.

        Args:
            channel_id: channel ID or @handle
            limit: maximum number of videos to fetch

        Returns:
            List of videos in unified format
        """
        try:
            # Resolve handle to channel ID if needed
            if not channel_id.startswith("UC") or "@" in channel_id:
                print(f"Resolving channel handle: {channel_id}")
                resolved_id = self._get_channel_id_by_handle(channel_id)
                if not resolved_id:
                    print(f"✗ Channel not found: {channel_id}")
                    return []
                channel_id = resolved_id
                print(f"✓ Resolved channel ID: {channel_id}")

            # Get the uploads playlist ID
            request = self.youtube.channels().list(
                part="contentDetails,snippet", id=channel_id
            )
            response = request.execute()

            if not response["items"]:
                print(f"✗ Channel not found: {channel_id}")
                return []

            channel_info = response["items"][0]
            channel_title = channel_info["snippet"]["title"]
            uploads_playlist_id = channel_info["contentDetails"]["relatedPlaylists"][
                "uploads"
            ]

            print(f"✓ Channel: {channel_title}")
            print(f"Fetching latest {limit} videos...")

            videos = []
            next_page_token = None

            while len(videos) < limit:
                request = self.youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=uploads_playlist_id,
                    maxResults=min(50, limit - len(videos)),
                    pageToken=next_page_token,
                )
                response = request.execute()

                for item in response["items"]:
                    video_id = item["contentDetails"]["videoId"]
                    snippet = item["snippet"]

                    videos.append(
                        {
                            "id": video_id,
                            "title": snippet["title"],
                            "description": snippet.get("description", "")[:500],
                            "date": snippet["publishedAt"],
                            "thumbnail": snippet["thumbnails"]["default"]["url"],
                        }
                    )

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            # Fetch statistics in batches of 50 (YouTube API limit)
            if videos:
                video_ids = [v["id"] for v in videos]
                stats_dict = {}

                batch_size = 50
                for i in range(0, len(video_ids), batch_size):
                    batch_ids = video_ids[i : i + batch_size]
                    stats_request = self.youtube.videos().list(
                        part="statistics", id=",".join(batch_ids)
                    )
                    stats_response = stats_request.execute()

                    for item in stats_response["items"]:
                        stats_dict[item["id"]] = item["statistics"]

                for video in videos:
                    stats = stats_dict.get(video["id"], {})
                    video["views"] = int(stats.get("viewCount", 0))
                    video["likes"] = int(stats.get("likeCount", 0))
                    video["comments_count"] = int(stats.get("commentCount", 0))

            print(f"✓ Fetched {len(videos)} videos")
            return videos

        except HttpError as e:
            print(f"✗ YouTube API error: {e}")
            return []
        except Exception as e:
            print(f"✗ Error fetching videos: {e}")
            return []

    async def get_post_comments(
        self, channel_id: str, post_id: str, existing_comment_ids: set = None
    ) -> List[Dict]:
        """
        Fetch comments for a video.

        Args:
            channel_id: channel ID (unused for YouTube but required by interface)
            post_id: video ID
            existing_comment_ids: set of already-fetched comment IDs

        Returns:
            List of new comments
        """
        if existing_comment_ids is None:
            existing_comment_ids = set()

        try:
            comments = []
            next_page_token = None
            new_count = 0

            while True:
                request = self.youtube.commentThreads().list(
                    part="snippet",
                    videoId=post_id,
                    maxResults=100,
                    pageToken=next_page_token,
                    textFormat="plainText",
                    order="time",
                )

                try:
                    response = request.execute()
                except HttpError as e:
                    if e.resp.status == 403:
                        print("  └─ Comments disabled")
                        return []
                    raise

                for item in response["items"]:
                    top_comment = item["snippet"]["topLevelComment"]
                    comment_id = top_comment["id"]

                    if comment_id in existing_comment_ids:
                        continue

                    snippet = top_comment["snippet"]

                    comment = {
                        "comment_id": comment_id,
                        "post_id": post_id,
                        "comment_type": "top_level",
                        "user": {
                            "id": snippet["authorChannelId"]["value"]
                            if "authorChannelId" in snippet
                            else snippet["authorDisplayName"],
                            "username": snippet["authorDisplayName"],
                            "first_name": snippet["authorDisplayName"],
                            "last_name": None,
                        },
                        "text": snippet["textDisplay"],
                        "date": snippet["publishedAt"],
                        "likes": snippet["likeCount"],
                    }

                    comments.append(comment)
                    new_count += 1

                    # Fetch replies if any
                    reply_count = item["snippet"]["totalReplyCount"]
                    if reply_count > 0:
                        replies = await self._get_comment_replies(
                            comment_id, post_id, existing_comment_ids
                        )
                        comments.extend(replies)
                        new_count += len(replies)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            if new_count > 0:
                print(f"  └─ Fetched {new_count} new comments")

            return comments

        except HttpError as e:
            print(f"  └─ ✗ YouTube API error: {e}")
            return []
        except Exception as e:
            print(f"  └─ ✗ Error: {e}")
            return []

    async def _get_comment_replies(
        self, comment_id: str, post_id: str, existing_comment_ids: set
    ) -> List[Dict]:
        """Fetch all replies to a comment (with pagination)."""
        try:
            replies = []
            next_page_token = None

            while True:
                request = self.youtube.comments().list(
                    part="snippet",
                    parentId=comment_id,
                    maxResults=100,
                    pageToken=next_page_token,
                    textFormat="plainText",
                )
                response = request.execute()

                for item in response["items"]:
                    reply_id = item["id"]

                    if reply_id in existing_comment_ids:
                        continue

                    snippet = item["snippet"]

                    reply = {
                        "comment_id": reply_id,
                        "post_id": post_id,
                        "comment_type": "reply",
                        "parent_id": comment_id,
                        "user": {
                            "id": snippet["authorChannelId"]["value"]
                            if "authorChannelId" in snippet
                            else snippet["authorDisplayName"],
                            "username": snippet["authorDisplayName"],
                            "first_name": snippet["authorDisplayName"],
                            "last_name": None,
                        },
                        "text": snippet["textDisplay"],
                        "date": snippet["publishedAt"],
                        "likes": snippet["likeCount"],
                    }

                    replies.append(reply)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            return replies

        except Exception:
            # Silently skip errors (e.g. deleted comments)
            return []

    async def sync_channel_data(
        self, channel_id: str, data_manager: ChannelDataManager, posts_limit: int = 50
    ) -> Dict:
        """
        Sync YouTube channel data (fetch new videos and comments).

        Args:
            channel_id: channel ID or @handle
            data_manager: data manager instance
            posts_limit: number of videos to check

        Returns:
            dict with sync statistics
        """
        await self.connect()

        print("\nPhase 1: Fetching data from YouTube")
        print("=" * 60)

        print(f"Fetching latest {posts_limit} videos...")
        videos = await self.get_posts(channel_id, posts_limit)

        if not videos:
            print("✗ No videos found")
            return None

        stats = {
            "total_posts": len(videos),
            "new_posts": 0,
            "updated_posts": 0,
            "skipped_posts": 0,
            "total_comments": 0,
            "new_comments": 0,
        }

        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=MAX_VIDEO_AGE_DAYS)

        print(
            f"\nProcessing videos (updating only videos newer than {MAX_VIDEO_AGE_DAYS} days):\n"
        )

        for i, video in enumerate(videos, 1):
            video_id = video["id"]
            video_date = datetime.fromisoformat(video["date"].replace("Z", "+00:00"))
            video_age_days = (now - video_date).days

            video_title = (
                video["title"][:50] + "..."
                if len(video["title"]) > 50
                else video["title"]
            )
            print(
                f"[{i}/{len(videos)}] {video_title} ({video_age_days}d ago)...", end=" "
            )

            comments_count = video.get("comments_count", 0)

            if data_manager.post_exists(video_id):
                if video_date < cutoff_date:
                    print("Skipped (older than threshold)")
                    stats["skipped_posts"] += 1
                else:
                    if comments_count == 0 and not data_manager.load_comments(video_id):
                        print("Skipped (comments disabled)")
                        stats["skipped_posts"] += 1
                    else:
                        print("Updating comments...")
                        existing_comments = data_manager.load_comments(video_id)
                        existing_ids = {c["comment_id"] for c in existing_comments}

                        new_comments = await self.get_post_comments(
                            channel_id, video_id, existing_ids
                        )

                        if new_comments:
                            all_comments = existing_comments + new_comments
                            data_manager.save_post_data(video_id, video, all_comments)
                            stats["new_comments"] += len(new_comments)
                            stats["total_comments"] += len(all_comments)
                            stats["updated_posts"] += 1
                        else:
                            stats["total_comments"] += len(existing_comments)
                            stats["skipped_posts"] += 1
            else:
                if comments_count == 0:
                    print("Skipped (comments disabled)")
                    data_manager.save_post_data(video_id, video, [])
                    stats["skipped_posts"] += 1
                else:
                    print("New video, downloading...")
                    comments = await self.get_post_comments(channel_id, video_id)
                    data_manager.save_post_data(video_id, video, comments)
                    stats["new_posts"] += 1
                    stats["new_comments"] += len(comments)
                    stats["total_comments"] += len(comments)

            await asyncio.sleep(0.1)

        channel_info = {
            "channel": channel_id,
            "last_sync": now.isoformat(),
            "posts_limit": posts_limit,
            "stats": stats,
        }
        data_manager.save_channel_info(channel_info)

        print(f"\n{'=' * 60}")
        print("Sync statistics:")
        print(f"  • Videos checked:   {stats['total_posts']}")
        print(f"  • New videos:       {stats['new_posts']}")
        print(f"  • Updated videos:   {stats['updated_posts']}")
        print(f"  • Skipped:          {stats['skipped_posts']}")
        print(f"  • Total comments:   {stats['total_comments']}")
        print(f"  • New comments:     {stats['new_comments']}")

        return stats
