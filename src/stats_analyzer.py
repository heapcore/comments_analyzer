"""
Comment statistics module.
"""

from collections import defaultdict
from typing import List, Dict
from pathlib import Path
from datetime import datetime, timezone
import json


def print_basic_statistics(
    comments: List[Dict], save_dir: Path = None, export_hate_file: str = None
) -> Dict:
    """
    Compute and print basic statistics without LLM analysis.

    Args:
        comments: list of comment dicts
        save_dir: directory to save statistics JSON
        export_hate_file: optional path for additional hate speech export

    Returns:
        dict with basic statistics
    """
    if not comments:
        print("✗ No comments to analyze")
        return {}

    stats = CommentsStatistics(comments)

    total_comments = len(comments)
    unique_users = stats.get_unique_users_count()

    # Comment type breakdown (YouTube)
    top_level_comments = [c for c in comments if c.get("comment_type") == "top_level"]
    reply_comments = [c for c in comments if c.get("comment_type") == "reply"]
    has_comment_types = len(top_level_comments) > 0 or len(reply_comments) > 0

    print(f"Total comments:           {total_comments}")
    print(f"Unique users:             {unique_users}")
    print(f"Avg comments per user:    {total_comments / unique_users:.1f}")

    if has_comment_types:
        print("\nComment types:")
        print(
            f"  • Top-level: {len(top_level_comments)} ({len(top_level_comments) / total_comments * 100:.1f}%)"
        )
        print(
            f"  • Replies:   {len(reply_comments)} ({len(reply_comments) / total_comments * 100:.1f}%)"
        )

    all_users = stats.get_top_users(len(stats.users_comments))

    top_groups = [(10, "top-10"), (100, "top-100"), (1000, "top-1000")]

    print("\nActivity distribution:")

    for top_n, label in top_groups:
        if len(all_users) >= top_n:
            top_users = all_users[:top_n]
            top_comments = sum(count for _, count, _ in top_users)
            percentage = (top_comments / total_comments) * 100
            print(f"  • {label} users: {top_comments} comments ({percentage:.1f}%)")

    top_10 = all_users[:10]
    print("\nTop-10 most active users:")
    for i, (user_id, count, username) in enumerate(top_10, 1):
        percentage = (count / total_comments) * 100
        display_name = username if username else f"User_{user_id}"
        print(f"  {i:2d}. {display_name}: {count} comments ({percentage:.1f}%)")

    user_distribution = stats.get_user_activity_distribution()
    print("\nUser activity distribution:")

    for label, data in user_distribution.items():
        users_count = data["users_count"]
        percentage = data["percentage"]

        if users_count > 0:
            print(f"  • {label:20s}: {users_count:5d} users ({percentage:5.1f}%)")

    # Top comments by likes (if available)
    comments_with_likes = [
        c for c in comments if "likes" in c and c.get("likes", 0) > 0
    ]
    if comments_with_likes:
        top_comments_by_likes = sorted(
            comments_with_likes, key=lambda x: x.get("likes", 0), reverse=True
        )[:10]

        print("\nTop-10 comments by likes:")
        for i, comment in enumerate(top_comments_by_likes, 1):
            likes = comment.get("likes", 0)
            username = (
                comment["user"].get("username")
                or comment["user"].get("first_name")
                or "Anonymous"
            )
            text = (
                comment["text"][:80] + "..."
                if len(comment["text"]) > 80
                else comment["text"]
            )
            print(f"  {i:2d}. {username:30s} - {likes:5d} likes")
            print(f"      {text}")

    print("\nActivity concentration (percentiles):")
    percentiles = [20, 40, 60, 80, 100]
    percentile_results = {}

    for percentile in percentiles:
        target_comments = (percentile / 100) * total_comments

        cumulative_comments = 0
        users_count = 0

        while cumulative_comments < target_comments and users_count < len(all_users):
            _, count, _ = all_users[users_count]
            cumulative_comments += count
            users_count += 1

        percentile_results[percentile] = {
            "users_count": users_count,
            "percentage_of_users": (users_count / unique_users) * 100,
        }

        print(
            f"  • {percentile:3d}% of comments written by {users_count:4d} most active users ({percentile_results[percentile]['percentage_of_users']:.1f}% of all)"
        )

    # Hate speech analysis
    from src.hate_speech_detector import HateSpeechDetector

    hate_detector = HateSpeechDetector()
    hate_stats = hate_detector.analyze_comments(comments)
    hate_detector.print_statistics(hate_stats)

    # Always save hate speech comments to hate_comments.json
    if hate_stats.get("comments_with_hate", 0) > 0 and save_dir:
        default_hate_file = save_dir / "hate_comments.json"
        hate_detector.export_hate_comments(hate_stats, str(default_hate_file))

    # Additional export if explicitly requested
    if export_hate_file and hate_stats.get("comments_with_hate", 0) > 0:
        if export_hate_file != str(save_dir / "hate_comments.json"):
            hate_detector.export_hate_comments(hate_stats, export_hate_file)

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_comments": total_comments,
        "unique_users": unique_users,
        "average_comments_per_user": round(total_comments / unique_users, 2),
        "user_activity_distribution": user_distribution,
        "hate_speech_stats": {
            "comments_with_hate": hate_stats.get("comments_with_hate", 0),
            "percentage": hate_stats.get("percentage", 0),
            "unique_users_with_hate": hate_stats.get("unique_users_with_hate", 0),
            "categories": hate_stats.get("categories_stats", {}),
            "top_matches": hate_stats.get("top_matches", []),
        },
        "top_groups": {},
    }

    for top_n, label in top_groups:
        if len(all_users) >= top_n:
            top_users = all_users[:top_n]
            top_comments = sum(count for _, count, _ in top_users)
            result["top_groups"][label] = {
                "users_count": top_n,
                "comments_count": top_comments,
                "percentage": round((top_comments / total_comments) * 100, 2),
            }

    result["top_10_users"] = [
        {
            "user_id": user_id,
            "username": username,
            "comments_count": count,
            "percentage": round((count / total_comments) * 100, 2),
        }
        for user_id, count, username in top_10
    ]

    result["percentiles"] = percentile_results

    if save_dir:
        stats_file = save_dir / "basic_statistics.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Basic statistics saved: {stats_file}")

    return result


class CommentsStatistics:
    """Computes statistics over a list of comments."""

    def __init__(self, comments: List[Dict]):
        self.comments = comments
        self.users_comments = defaultdict(list)
        self._group_comments_by_user()

    def _group_comments_by_user(self):
        """Group comments by user ID."""
        for comment in self.comments:
            user_id = comment["user"]["id"]
            self.users_comments[user_id].append(comment)

    def get_unique_users_count(self) -> int:
        """Return number of unique users."""
        return len(self.users_comments)

    def get_top_users(self, limit=100) -> List[tuple]:
        """
        Return top users by comment count.

        Args:
            limit: maximum number of users to return

        Returns:
            List of (user_id, comment_count, username) tuples sorted by count descending
        """
        users_count = []
        for user_id, comments in self.users_comments.items():
            username = (
                comments[0]["user"].get("username")
                or comments[0]["user"].get("first_name")
                or "Anonymous"
            )
            users_count.append((user_id, len(comments), username))

        users_count.sort(key=lambda x: x[1], reverse=True)
        return users_count[:limit]

    def get_total_comments_from_top_users(self, top_users: List[tuple]) -> int:
        """Return total comment count from a list of top users."""
        return sum(count for _, count, _ in top_users)

    def get_user_activity_distribution(self) -> Dict:
        """
        Return distribution of users by comment count.

        Returns:
            Dict mapping group labels to {users_count, percentage}
        """
        comments_per_user = [len(comments) for comments in self.users_comments.values()]
        total_users = len(comments_per_user)

        groups = [
            (1, 1, "1 comment"),
            (2, 2, "2 comments"),
            (3, 3, "3 comments"),
            (4, 4, "4 comments"),
            (5, 5, "5 comments"),
            (6, 10, "6-10 comments"),
            (11, 20, "11-20 comments"),
            (21, 50, "21-50 comments"),
            (51, 100, "51-100 comments"),
            (101, 200, "101-200 comments"),
            (201, 500, "201-500 comments"),
            (501, float("inf"), "501+ comments"),
        ]

        distribution = {}

        for min_val, max_val, label in groups:
            count = sum(1 for c in comments_per_user if min_val <= c <= max_val)
            percentage = (count / total_users * 100) if total_users > 0 else 0

            distribution[label] = {"users_count": count, "percentage": percentage}

        return distribution

    def print_basic_stats(self):
        """Print basic statistics summary."""
        print("\nBASIC STATISTICS:")
        print(f"  • Total comments: {len(self.comments)}")
        print(f"  • Unique users:   {self.get_unique_users_count()}")

        top_users = self.get_top_users(100)
        total_top = self.get_total_comments_from_top_users(top_users)

        print("\nTOP-100 USERS:")
        print(f"  • Total comments from top-100: {total_top}")
        print(
            f"  • Percentage of all comments:  {total_top / len(self.comments) * 100:.1f}%"
        )

        print("\nTop-10 most active:")
        for i, (user_id, count, username) in enumerate(top_users[:10], 1):
            print(f"  {i}. {username} (ID: {user_id}): {count} comments")


def analyze_comments_and_save(
    comments: List[Dict],
    save_dir: Path = None,
    save_interval: int = 100,
    force_reanalysis: bool = False,
) -> Dict:
    """
    Run full LLM-based analysis and save results.

    Args:
        comments: list of comment dicts
        save_dir: directory for saving intermediate and final results
        save_interval: save every N comments
        force_reanalysis: if True, ignore existing results and reanalyze everything

    Returns:
        dict with analysis results
    """
    if not comments:
        print("✗ No comments to analyze")
        return {}

    existing_results = {}
    analyzed_comment_ids = set()

    if force_reanalysis:
        print("\nForce reanalysis mode — all comments will be re-analyzed.")
        if save_dir:
            analysis_file = save_dir / "latest_analysis.json"
            if analysis_file.exists():
                analysis_file.unlink()
                print("  └─ Previous results deleted")
    elif save_dir:
        analysis_file = save_dir / "latest_analysis.json"
        if analysis_file.exists():
            try:
                with open(analysis_file, "r", encoding="utf-8") as f:
                    existing_results = json.load(f)

                if "comments_with_analysis" in existing_results:
                    for comment_data in existing_results["comments_with_analysis"]:
                        if "toxicity" in comment_data and "political" in comment_data:
                            analyzed_comment_ids.add(comment_data["comment_id"])

                    if analyzed_comment_ids:
                        print("\nResuming from previous run:")
                        print(
                            f"  └─ Already analyzed: {len(analyzed_comment_ids)} comments"
                        )
                        print(
                            f"  └─ Remaining:        {len(comments) - len(analyzed_comment_ids)} comments"
                        )
            except Exception as e:
                print(f"\n⚠ Could not load previous results: {e}")
                existing_results = {}
                analyzed_comment_ids = set()

    comments_to_analyze = [
        c for c in comments if c["comment_id"] not in analyzed_comment_ids
    ]

    if not comments_to_analyze:
        print("\n✓ All comments already analyzed.")
        return existing_results

    print(f"\nAnalyzing {len(comments_to_analyze)} new comments...")

    stats = CommentsStatistics(comments)
    stats.print_basic_stats()

    # Toxicity analysis
    from src.toxicity_analyzer import ToxicityAnalyzer

    print("\n" + "=" * 60)
    print("TOXICITY ANALYSIS")
    print("=" * 60)

    toxicity_analyzer = ToxicityAnalyzer()
    new_toxicity_results = toxicity_analyzer.analyze_all_comments(comments_to_analyze)

    # Merge with existing results
    if existing_results and "toxicity_analysis" in existing_results:
        toxicity_by_comment = existing_results["toxicity_analysis"].get(
            "toxicity_by_comment", {}
        )
        toxicity_by_user = existing_results["toxicity_analysis"].get(
            "toxicity_by_user", {}
        )

        toxicity_by_comment.update(new_toxicity_results.get("toxicity_by_comment", {}))
        for user_id, toxicities in new_toxicity_results.get(
            "toxicity_by_user", {}
        ).items():
            if user_id in toxicity_by_user:
                toxicity_by_user[user_id].extend(toxicities)
            else:
                toxicity_by_user[user_id] = toxicities

        toxicity_results = {
            "toxicity_by_comment": toxicity_by_comment,
            "toxicity_by_user": toxicity_by_user,
            "users_stats": new_toxicity_results.get("users_stats", {}),
        }
    else:
        toxicity_results = new_toxicity_results

    # Save intermediate toxicity results
    if save_dir:
        temp_file = save_dir / "toxicity_temp.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(toxicity_results, f, ensure_ascii=False, indent=2)

    toxicity_analyzer.print_toxicity_stats(toxicity_results)

    # Political alignment analysis
    from src.political_analyzer import PoliticalAnalyzer

    print("\n" + "=" * 60)
    print("POLITICAL ALIGNMENT ANALYSIS")
    print("=" * 60)

    political_analyzer = PoliticalAnalyzer()
    new_political_results = political_analyzer.analyze_all_comments(comments_to_analyze)

    # Merge with existing results
    if existing_results and "political_analysis" in existing_results:
        political_by_comment = existing_results["political_analysis"].get(
            "political_by_comment", {}
        )
        political_by_user = existing_results["political_analysis"].get(
            "political_by_user", {}
        )

        political_by_comment.update(
            new_political_results.get("political_by_comment", {})
        )
        for user_id, politicals in new_political_results.get(
            "political_by_user", {}
        ).items():
            if user_id in political_by_user:
                political_by_user[user_id].extend(politicals)
            else:
                political_by_user[user_id] = politicals

        political_results = {
            "political_by_comment": political_by_comment,
            "political_by_user": political_by_user,
            "users_stats": new_political_results.get("users_stats", {}),
        }
    else:
        political_results = new_political_results

    # Save intermediate political results
    if save_dir:
        temp_file = save_dir / "political_temp.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(political_results, f, ensure_ascii=False, indent=2)

    political_analyzer.print_political_stats(political_results)

    # Compile final results
    top_users = stats.get_top_users(100)

    results = {
        "total_comments": len(comments),
        "unique_users": stats.get_unique_users_count(),
        "top_100_users": [
            {"user_id": user_id, "username": username, "comments_count": count}
            for user_id, count, username in top_users
        ],
        "top_100_total": stats.get_total_comments_from_top_users(top_users),
        "toxicity_analysis": toxicity_results,
        "political_analysis": political_results,
        "comments_with_analysis": [],
    }

    for comment in comments:
        comment_data = comment.copy()
        comment_id = comment["comment_id"]

        if comment_id in toxicity_results.get("comments_toxicity", {}):
            comment_data["toxicity"] = toxicity_results["comments_toxicity"][comment_id]

        if comment_id in political_results.get("comments_political", {}):
            comment_data["political"] = political_results["comments_political"][
                comment_id
            ]

        results["comments_with_analysis"].append(comment_data)

    return results
