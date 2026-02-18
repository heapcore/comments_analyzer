"""
Political alignment analysis module using LM Studio local LLM API.
"""

from typing import List, Dict
from collections import Counter, defaultdict
import os
import requests
import time
from tqdm import tqdm


class PoliticalAnalyzer:
    """Classifies comments as pro_ukraine, pro_russia, or neutral via LM Studio API."""

    def __init__(self, api_url=None, batch_size=None):
        """Initialize the analyzer."""
        self.api_url = api_url or os.getenv(
            "LM_STUDIO_API_URL", "http://localhost:1234/v1/chat/completions"
        )
        self.batch_size = batch_size or int(os.getenv("BATCH_SIZE", "5"))
        self._check_api_connection()

    def _check_api_connection(self):
        """Verify connection to LM Studio API."""
        try:
            response = requests.get(
                self.api_url.replace("/v1/chat/completions", "/v1/models"), timeout=5
            )
            if response.status_code == 200:
                print("✓ Connected to LM Studio API (political analyzer)")
                return True
            else:
                print(
                    "✗ LM Studio API unavailable. Make sure LM Studio is running with a model loaded."
                )
                raise ConnectionError("LM Studio API unavailable")
        except requests.exceptions.RequestException as e:
            print(f"✗ Cannot connect to LM Studio: {e}")
            raise ConnectionError("Cannot connect to LM Studio API")

    def _analyze_text_with_llm(self, texts: List[str]) -> List[str]:
        """
        Classify political alignment of a batch of texts using LLM.

        Args:
            texts: list of comment texts

        Returns:
            list of categories: 'pro_ukraine', 'pro_russia', 'neutral'
        """
        if not texts:
            return []

        comments_text = "\n".join(
            [f"{i + 1}. {text[:300]}" for i, text in enumerate(texts)]
        )
        format_lines = "\n".join([f"{i + 1}:category" for i in range(len(texts))])

        prompt = f"""Classify the political stance of each comment.

COMMENTS:
{comments_text}

CATEGORIES:
- pro_ukraine (supporting Ukraine, criticizing Russia)
- pro_russia (supporting Russia, criticizing Ukraine)
- neutral (neutral stance)

Response format (strict):
{format_lines}

Example:
1:pro_ukraine
2:neutral
3:pro_russia

Your response (NO explanations):"""

        try:
            response = requests.post(
                self.api_url,
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 25 * len(texts),
                    "stop": ["\n\n\n", "Comments:", "COMMENTS", "Explanation"],
                },
                timeout=max(30, len(texts) * 2),
            )

            if response.status_code != 200:
                raise Exception(f"API returned status {response.status_code}")

            result = response.json()
            message = result["choices"][0]["message"]
            answer = message.get("content", "").strip()

            # Fall back to reasoning field for reasoning models (e.g. GPT-OSS)
            if not answer and "reasoning" in message:
                answer = message["reasoning"].strip()

            results = []
            for line in answer.split("\n"):
                line = line.strip()

                # Skip preamble lines the model may generate
                if (
                    "here is" in line.lower()
                    or "analysis" in line.lower()
                    or "based on" in line.lower()
                ):
                    continue

                if not line or ":" not in line:
                    continue

                parts = line.split(":", 1)
                if len(parts) == 2:
                    try:
                        num = int(parts[0].strip())
                    except ValueError:
                        continue

                    category_text = parts[1].strip().lower().replace("-", "_")

                    if (
                        "pro_ukraine" in category_text
                        or "ukraine" in category_text
                        or "ukr" in category_text
                    ):
                        results.append("pro_ukraine")
                    elif (
                        "pro_russia" in category_text
                        or "russia" in category_text
                        or "rus" in category_text
                    ):
                        results.append("pro_russia")
                    else:
                        results.append("neutral")

            # Pad to expected length
            while len(results) < len(texts):
                results.append("neutral")

            return results[: len(texts)]

        except Exception:
            # Fall back to neutral on error
            return ["neutral"] * len(texts)

    def analyze_all_comments(self, comments: List[Dict]) -> Dict:
        """
        Analyze political alignment of all comments.

        Args:
            comments: list of comment dicts

        Returns:
            dict with analysis results
        """
        print("Analyzing political alignment via LLM...")

        political_by_comment = {}
        political_by_user = defaultdict(list)
        failed_batches = []

        pbar = tqdm(
            total=len(comments),
            desc="Political",
            unit="comm",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )

        for i in range(0, len(comments), self.batch_size):
            batch = comments[i : i + self.batch_size]
            texts = [comment.get("text", "") or "" for comment in batch]

            politicals = self._analyze_text_with_llm(texts)

            if len(politicals) != len(texts):
                print(
                    f"\n⚠ Batch error: got {len(politicals)} results instead of {len(texts)}"
                )
                failed_batches.append((batch, texts))
                politicals = ["neutral"] * len(texts)

            for comment, political in zip(batch, politicals):
                comment_id = comment["comment_id"]
                user_id = comment["user"]["id"]
                political_by_comment[comment_id] = political
                political_by_user[user_id].append(political)

            pbar.update(len(batch))

        pbar.close()

        # Retry failed batches once
        if failed_batches:
            print(f"\nRetrying {len(failed_batches)} failed batches...")
            retry_pbar = tqdm(
                total=len(failed_batches),
                desc="Retry",
                unit="batch",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
            )

            for batch, texts in failed_batches:
                politicals = self._analyze_text_with_llm(texts)

                if len(politicals) == len(texts):
                    for comment, political in zip(batch, politicals):
                        comment_id = comment["comment_id"]
                        user_id = comment["user"]["id"]
                        political_by_comment[comment_id] = political
                        political_by_user[user_id] = [
                            p for p in political_by_user[user_id] if p != "neutral"
                        ] + [political]
                else:
                    print(f"\n⚠ Batch failed again: {len(politicals)}/{len(texts)}")

                retry_pbar.update(1)
                time.sleep(0.2)

            retry_pbar.close()

        print(f"✓ Analyzed {len(comments)} comments")

        # Aggregate per-user stats
        users_political_stats = {}
        for user_id, politicals in political_by_user.items():
            counter = Counter(politicals)
            total = len(politicals)

            pro_ukraine_pct = counter["pro_ukraine"] / total
            pro_russia_pct = counter["pro_russia"] / total

            # Assign dominant category if at least 20% of comments have a clear stance
            if pro_ukraine_pct >= 0.2 and pro_ukraine_pct > pro_russia_pct:
                dominant_category = "pro_ukraine"
            elif pro_russia_pct >= 0.2 and pro_russia_pct > pro_ukraine_pct:
                dominant_category = "pro_russia"
            else:
                dominant_category = "neutral"

            users_political_stats[user_id] = {
                "dominant": dominant_category,
                "pro_ukraine_count": counter["pro_ukraine"],
                "pro_russia_count": counter["pro_russia"],
                "neutral_count": counter["neutral"],
                "total": total,
            }

        return {
            "comments_political": political_by_comment,
            "users_political": users_political_stats,
            "total_stats": self._calculate_total_stats(
                political_by_comment, users_political_stats
            ),
        }

    def _calculate_total_stats(
        self, comments_political: Dict, users_political: Dict
    ) -> Dict:
        """Calculate aggregate statistics."""
        comments_counter = Counter(comments_political.values())
        users_categories = [
            user_data["dominant"] for user_data in users_political.values()
        ]
        users_counter = Counter(users_categories)

        return {
            "comments": {
                "pro_ukraine": comments_counter["pro_ukraine"],
                "pro_russia": comments_counter["pro_russia"],
                "neutral": comments_counter["neutral"],
                "total": len(comments_political),
            },
            "users": {
                "pro_ukraine": users_counter["pro_ukraine"],
                "pro_russia": users_counter["pro_russia"],
                "neutral": users_counter["neutral"],
                "total": len(users_political),
            },
        }

    def print_political_stats(self, results: Dict):
        """Print political alignment statistics to console."""
        stats = results["total_stats"]

        print("\nComment statistics:")
        total_comments = stats["comments"]["total"]
        print(
            f"  • Pro-Ukraine: {stats['comments']['pro_ukraine']} ({stats['comments']['pro_ukraine'] / total_comments * 100:.1f}%)"
        )
        print(
            f"  • Pro-Russia:  {stats['comments']['pro_russia']} ({stats['comments']['pro_russia'] / total_comments * 100:.1f}%)"
        )
        print(
            f"  • Neutral:     {stats['comments']['neutral']} ({stats['comments']['neutral'] / total_comments * 100:.1f}%)"
        )

        print("\nUser statistics:")
        total_users = stats["users"]["total"]
        print(
            f"  • Pro-Ukraine stance: {stats['users']['pro_ukraine']} ({stats['users']['pro_ukraine'] / total_users * 100:.1f}%)"
        )
        print(
            f"  • Pro-Russia stance:  {stats['users']['pro_russia']} ({stats['users']['pro_russia'] / total_users * 100:.1f}%)"
        )
        print(
            f"  • Neutral stance:     {stats['users']['neutral']} ({stats['users']['neutral'] / total_users * 100:.1f}%)"
        )
