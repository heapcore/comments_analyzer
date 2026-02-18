"""
Keyword-based hate speech detector for Russian and Ukrainian language comments.
No LLM required — uses compiled regex patterns for offline, instant detection.
"""

import re
from typing import List, Dict
from collections import defaultdict
from pathlib import Path


class HateSpeechDetector:
    """Keyword-based hate speech detector using prefix regex patterns."""

    def __init__(self):
        # Keyword patterns in Russian/Ukrainian (the only supported languages)
        self.hate_patterns = {
            "death_wishes": [
                "смерть москал",
                "смерть орк",
                "смерть русск",
                "смерть русн",
                "смерть росіян",
                "вбивати москал",
                "вбивати русск",
                "убивать москал",
                "убивать русск",
                "боже бомб",
                "боже, бомб",
            ],
            "ethnic_slurs": [
                "русорез",
                "русоріз",
                "москал",
                "кацап",
                "чурк",
                "узки",
                "уззки",
                "уzки",
                "уzzки",
                "рузг",
                "руззг",
                "руzг",
                "руzzг",
                "монгол",
                "орд",
            ],
            "dehumanization": [
                "хуйл",
                "пыня",
                "пыни",
                "пыне",
                "пыню",
                "пынi",
                "пып",
                "орк",
                "ватник",
                "ват",
                "ватян",
                "совок",
                "совк",
                "русн",
                "рашк",
                "раша",
                "раши",
                "рашe",
                "мордор",
                "русак",
                "руz",
                "роz",
                "пидор",
                "пидар",
                "жмур",
                "оккупант",
                "окупант",
                "перде",
            ],
            "violence_calls": [
                "порва",
                "вирізат",
                "вырезат",
                "знищ",
                "уничтож",
                "спалит",
                "сжечь",
                "сожг",
                "сожж",
                "розірва",
                "разорва",
                "бомбi",
            ],
        }

        # Compile regex patterns for efficient matching
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for all categories."""
        self.compiled_patterns = {}

        for category, phrases in self.hate_patterns.items():
            patterns = []
            for phrase in phrases:
                escaped = re.escape(phrase)
                # Allow multiple spaces between words
                escaped = escaped.replace(r"\ ", r"\s+")
                patterns.append(escaped)

            # Left word boundary only — allows prefix matching (e.g. 'орк' matches 'орков')
            combined_pattern = r"\b(?:" + "|".join(patterns) + r")"
            self.compiled_patterns[category] = re.compile(
                combined_pattern, re.IGNORECASE | re.UNICODE
            )

    def check_comment(self, comment_text: str) -> Dict:
        """
        Check a single comment for hate speech.

        Args:
            comment_text: comment text

        Returns:
            Dict with detection results
        """
        if not comment_text:
            return {"has_hate_speech": False, "categories": [], "matches": []}

        text_lower = comment_text.lower()
        found_categories = []
        all_matches = []

        for category, pattern in self.compiled_patterns.items():
            matches = pattern.findall(text_lower)
            if matches:
                found_categories.append(category)
                all_matches.extend(matches)

        return {
            "has_hate_speech": len(found_categories) > 0,
            "categories": found_categories,
            "matches": list(set(all_matches)),
        }

    def analyze_comments(self, comments: List[Dict]) -> Dict:
        """
        Analyze a list of comments for hate speech.

        Args:
            comments: list of comment dicts

        Returns:
            Dict with statistics
        """
        if not comments:
            return {}

        total_comments = len(comments)
        comments_with_hate = 0
        categories_count = defaultdict(int)
        matches_count = defaultdict(int)
        users_with_hate = set()
        comments_by_category = defaultdict(list)
        hate_comments_list = []

        results_by_comment = {}

        for comment in comments:
            comment_id = comment["comment_id"]
            text = comment["text"]
            user_id = comment["user"]["id"]

            result = self.check_comment(text)
            results_by_comment[comment_id] = result

            if result["has_hate_speech"]:
                comments_with_hate += 1
                users_with_hate.add(user_id)
                hate_comments_list.append(comment)

                for category in result["categories"]:
                    categories_count[category] += 1
                    comments_by_category[category].append(
                        {
                            "comment_id": comment_id,
                            "user": comment["user"].get("username")
                            or comment["user"].get("first_name")
                            or "Unknown",
                            "text": text,
                            "matches": result["matches"],
                        }
                    )

                for match in result["matches"]:
                    matches_count[match] += 1

        stats = {
            "total_comments": total_comments,
            "comments_with_hate": comments_with_hate,
            "percentage": round((comments_with_hate / total_comments * 100), 2)
            if total_comments > 0
            else 0,
            "unique_users_with_hate": len(users_with_hate),
            "categories_stats": dict(categories_count),
            "top_matches": sorted(
                matches_count.items(), key=lambda x: x[1], reverse=True
            )[:20],
            "comments_by_category": dict(comments_by_category),
            "results_by_comment": results_by_comment,
            "hate_comments_list": hate_comments_list,
        }

        return stats

    def print_statistics(self, stats: Dict):
        """Print hate speech statistics to console."""
        if not stats:
            print("✗ No data to analyze")
            return

        total = stats["total_comments"]
        with_hate = stats["comments_with_hate"]
        percentage = stats["percentage"]
        hate_comments = stats.get("hate_comments_list", [])

        print("\n" + "=" * 60)
        print("HATE SPEECH ANALYSIS (keyword-based, no LLM)")
        print("=" * 60)

        print("\nOverall statistics:")
        print(f"  • Total comments:            {total}")
        print(f"  • With hate speech:          {with_hate} ({percentage}%)")
        print(f"  • Unique users with hate:    {stats['unique_users_with_hate']}")

        # Comment type breakdown (YouTube)
        if hate_comments:
            top_level_hate = [
                c for c in hate_comments if c.get("comment_type") == "top_level"
            ]
            reply_hate = [c for c in hate_comments if c.get("comment_type") == "reply"]

            if len(top_level_hate) > 0 or len(reply_hate) > 0:
                print("\nHate speech by comment type:")
                if len(top_level_hate) > 0:
                    print(
                        f"  • Top-level: {len(top_level_hate)} ({len(top_level_hate) / with_hate * 100:.1f}%)"
                    )
                if len(reply_hate) > 0:
                    print(
                        f"  • Replies:   {len(reply_hate)} ({len(reply_hate) / with_hate * 100:.1f}%)"
                    )

        if stats["categories_stats"]:
            print("\nBy category:")
            category_names = {
                "death_wishes": "Death Wishes",
                "ethnic_slurs": "Ethnic Slurs",
                "dehumanization": "Dehumanization",
                "violence_calls": "Violence Calls",
            }

            for category, count in sorted(
                stats["categories_stats"].items(), key=lambda x: x[1], reverse=True
            ):
                cat_name = category_names.get(category, category)
                cat_percentage = round((count / total * 100), 2)
                print(f"  • {cat_name:20s}: {count:5d} ({cat_percentage}%)")

        if stats["top_matches"]:
            print("\nTop-20 matched phrases:")
            for i, (match, count) in enumerate(stats["top_matches"], 1):
                match_percentage = round((count / total * 100), 2)
                print(f"  {i:2d}. {match:30s}: {count:5d} ({match_percentage}%)")

        if hate_comments:
            self._print_user_statistics(hate_comments)

        print("\n" + "=" * 60)

    def _print_user_statistics(self, hate_comments: List[Dict]):
        """Print detailed per-user hate speech statistics."""

        users_comments = defaultdict(list)
        for comment in hate_comments:
            user_id = comment["user"]["id"]
            users_comments[user_id].append(comment)

        total_hate_comments = len(hate_comments)
        unique_users = len(users_comments)

        users_list = []
        for user_id, comments in users_comments.items():
            username = (
                comments[0]["user"].get("username")
                or comments[0]["user"].get("first_name")
                or f"User_{user_id}"
            )
            users_list.append((user_id, len(comments), username))

        users_list.sort(key=lambda x: x[1], reverse=True)

        print("\nActivity distribution (hate speech):")
        for top_n, label in [(10, "top-10"), (100, "top-100"), (1000, "top-1000")]:
            if len(users_list) >= top_n:
                top_users = users_list[:top_n]
                top_comments_count = sum(count for _, count, _ in top_users)
                percentage = (top_comments_count / total_hate_comments) * 100
                print(
                    f"  • {label} users: {top_comments_count} comments ({percentage:.1f}%)"
                )

        print("\nTop-10 users with hate speech:")
        for i, (user_id, count, username) in enumerate(users_list[:10], 1):
            percentage = (count / total_hate_comments) * 100
            print(f"  {i:2d}. {username:30s}: {count} comments ({percentage:.1f}%)")

        print("\nUser activity distribution (hate speech):")
        comments_per_user = [len(comments) for comments in users_comments.values()]

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
            (101, float("inf"), "101+ comments"),
        ]

        for min_val, max_val, label in groups:
            count = sum(1 for c in comments_per_user if min_val <= c <= max_val)
            if count > 0:
                percentage = count / unique_users * 100
                print(f"  • {label:20s}: {count:5d} users ({percentage:5.1f}%)")

        # Top comments by likes
        comments_with_likes = [
            c for c in hate_comments if "likes" in c and c.get("likes", 0) > 0
        ]
        if comments_with_likes:
            top_by_likes = sorted(
                comments_with_likes, key=lambda x: x.get("likes", 0), reverse=True
            )[:10]

            print("\nTop-10 hate speech comments by likes:")
            for i, comment in enumerate(top_by_likes, 1):
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

        print("\nActivity concentration (percentiles, hate speech):")
        percentiles = [20, 40, 60, 80, 100]

        for percentile in percentiles:
            target_comments = (percentile / 100) * total_hate_comments

            cumulative_comments = 0
            users_count = 0

            while cumulative_comments < target_comments and users_count < len(
                users_list
            ):
                _, count, _ = users_list[users_count]
                cumulative_comments += count
                users_count += 1

            percentage_of_users = (users_count / unique_users) * 100
            print(
                f"  • {percentile:3d}% of comments written by {users_count:4d} most active users ({percentage_of_users:.1f}% of all)"
            )

    def get_category_examples(
        self, stats: Dict, category: str, limit: int = 5
    ) -> List[Dict]:
        """
        Get example comments for a category.

        Args:
            stats: statistics from analyze_comments
            category: category name
            limit: maximum number of examples

        Returns:
            List of example comments
        """
        comments = stats.get("comments_by_category", {}).get(category, [])
        return comments[:limit]

    def export_hate_comments(self, stats: Dict, output_file: str) -> bool:
        """
        Export hate speech comments to a JSON file.

        Args:
            stats: statistics from analyze_comments
            output_file: output file path

        Returns:
            True if successful, False otherwise
        """
        import json
        from datetime import datetime, timezone

        hate_comments = stats.get("hate_comments_list", [])
        results_by_comment = stats.get("results_by_comment", {})

        if not hate_comments:
            print("✗ No hate speech comments to export")
            return False

        # Collect all matches (not just top-20)
        all_matches_dict = {}
        for comment in hate_comments:
            comment_id = comment["comment_id"]
            hate_result = results_by_comment.get(comment_id, {})
            for match in hate_result.get("matches", []):
                all_matches_dict[match] = all_matches_dict.get(match, 0) + 1

        all_matches_sorted = sorted(
            all_matches_dict.items(), key=lambda x: x[1], reverse=True
        )

        export_data = {
            "metadata": {
                "export_date": datetime.now(timezone.utc).isoformat(),
                "total_comments": stats["total_comments"],
                "comments_with_hate": stats["comments_with_hate"],
                "percentage": stats["percentage"],
                "unique_users_with_hate": stats["unique_users_with_hate"],
            },
            "categories_stats": stats.get("categories_stats", {}),
            "top_matches": dict(stats.get("top_matches", [])),
            "all_matches": dict(all_matches_sorted),
            "comments": [],
        }

        for comment in hate_comments:
            comment_id = comment["comment_id"]
            hate_result = results_by_comment.get(comment_id, {})

            export_comment = {
                "comment_id": comment_id,
                "post_id": comment.get("post_id"),
                "user": {
                    "id": comment["user"]["id"],
                    "username": comment["user"].get("username"),
                    "first_name": comment["user"].get("first_name"),
                },
                "text": comment["text"],
                "date": comment.get("date"),
                "likes": comment.get("likes", 0),
                "comment_type": comment.get("comment_type"),
                "hate_speech": {
                    "categories": hate_result.get("categories", []),
                    "matches": hate_result.get("matches", []),
                },
            }

            export_data["comments"].append(export_comment)

        # Sort by likes descending
        export_data["comments"].sort(key=lambda x: x["likes"], reverse=True)

        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            print(
                f"\n✓ Exported {len(hate_comments)} hate speech comments: {output_path}"
            )

            # Also export as plain text (one comment per line, for LLM analysis)
            txt_file = output_path.with_suffix(".txt")
            self._export_to_txt(export_data["comments"], txt_file)

            return True

        except Exception as e:
            print(f"\n✗ Export error: {e}")
            return False

    def _export_to_txt(self, comments: List[Dict], txt_file: Path):
        """
        Export comments to a plain text file (one per line).

        Args:
            comments: list of comment dicts
            txt_file: output file path
        """
        try:
            with open(txt_file, "w", encoding="utf-8") as f:
                for comment in comments:
                    text = comment.get("text", "")
                    text = (
                        text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
                    )
                    text = " ".join(text.split())
                    f.write(text + "\n")

            print(f"✓ Plain text export (for LLM): {txt_file}")

        except Exception as e:
            print(f"✗ Error writing text file: {e}")


def analyze_hate_speech_and_print(comments: List[Dict]) -> Dict:
    """
    Analyze hate speech in a list of comments and print results.

    Args:
        comments: list of comment dicts

    Returns:
        Dict with statistics
    """
    if not comments:
        print("✗ No comments to analyze")
        return {}

    detector = HateSpeechDetector()
    stats = detector.analyze_comments(comments)
    detector.print_statistics(stats)

    return stats
