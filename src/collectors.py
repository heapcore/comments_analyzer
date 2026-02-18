"""
Base classes for comment collectors from different sources.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path
import json


class ChannelDataManager:
    """Universal data manager for a channel (Telegram or YouTube)."""

    def __init__(self, channel_name: str, source: str = "telegram"):
        """
        Args:
            channel_name: channel identifier
            source: data source ('telegram' or 'youtube')
        """
        self.channel_name = self._normalize_name(channel_name)
        self.source = source
        self.base_dir = Path("data") / self.source / self.channel_name
        self.posts_dir = self.base_dir / "posts"
        self.analysis_dir = self.base_dir / "analysis"
        self.channel_info_file = self.base_dir / "channel_info.json"

        # Create directory structure
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_name(self, name: str) -> str:
        """Normalize channel name for use as a directory name."""
        clean = name.strip().lstrip("@").replace(" ", "_")
        return "".join(c for c in clean if c.isalnum() or c in ("_", "-"))

    def get_post_dir(self, post_id: str) -> Path:
        """Return the directory path for a post."""
        return self.posts_dir / str(post_id)

    def post_exists(self, post_id: str) -> bool:
        """Check whether a post directory exists."""
        return self.get_post_dir(post_id).exists()

    def load_post_info(self, post_id: str) -> Optional[dict]:
        """Load post metadata."""
        post_info_file = self.get_post_dir(post_id) / "post_info.json"
        if post_info_file.exists():
            with open(post_info_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def load_comments(self, post_id: str) -> list:
        """Load comments for a post."""
        comments_file = self.get_post_dir(post_id) / "comments.json"
        if comments_file.exists():
            with open(comments_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_post_data(self, post_id: str, post_info: dict, comments: list):
        """Save post data and comments."""
        post_dir = self.get_post_dir(post_id)
        post_dir.mkdir(exist_ok=True)

        with open(post_dir / "post_info.json", "w", encoding="utf-8") as f:
            json.dump(post_info, f, ensure_ascii=False, indent=2)

        with open(post_dir / "comments.json", "w", encoding="utf-8") as f:
            json.dump(comments, f, ensure_ascii=False, indent=2)

    def get_all_post_ids(self) -> list:
        """Return IDs of all saved posts."""
        if not self.posts_dir.exists():
            return []
        return [d.name for d in self.posts_dir.iterdir() if d.is_dir()]

    def load_all_comments(self) -> list:
        """Load all comments from all posts."""
        all_comments = []
        for post_id in self.get_all_post_ids():
            comments = self.load_comments(post_id)
            all_comments.extend(comments)
        return all_comments

    def save_channel_info(self, info: dict):
        """Save channel metadata."""
        with open(self.channel_info_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

    def load_channel_info(self) -> dict:
        """Load channel metadata."""
        if self.channel_info_file.exists():
            with open(self.channel_info_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}


class CommentsCollector(ABC):
    """Abstract base class for comment collectors."""

    @abstractmethod
    async def connect(self):
        """Connect to the service."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the service."""
        pass

    @abstractmethod
    async def get_posts(self, channel_id: str, limit: int) -> List[Dict]:
        """
        Fetch a list of posts from a channel.

        Args:
            channel_id: channel identifier
            limit: maximum number of posts to fetch

        Returns:
            List of posts in unified format
        """
        pass

    @abstractmethod
    async def get_post_comments(
        self, channel_id: str, post_id: str, existing_comment_ids: set = None
    ) -> List[Dict]:
        """
        Fetch comments for a post.

        Args:
            channel_id: channel identifier
            post_id: post identifier
            existing_comment_ids: set of already-known comment IDs for incremental updates

        Returns:
            List of new comments in unified format
        """
        pass

    @abstractmethod
    async def sync_channel_data(
        self, channel_id: str, data_manager: ChannelDataManager, posts_limit: int
    ) -> Dict:
        """
        Sync channel data (fetch new posts and comments).

        Args:
            channel_id: channel identifier
            data_manager: data manager instance
            posts_limit: number of posts to check

        Returns:
            Dict with sync statistics
        """
        pass
