"""
Toxicity analysis module using LM Studio local LLM API.
"""

from typing import List, Dict
from collections import Counter, defaultdict
import os
import requests
import time
from tqdm import tqdm


class ToxicityAnalyzer:
    """Classifies comments as toxic, neutral, or friendly via LM Studio API."""

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
                print("✓ Connected to LM Studio API")
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
        Classify toxicity of a batch of texts using LLM.

        Args:
            texts: list of comment texts

        Returns:
            list of categories: 'toxic', 'neutral', 'friendly'
        """
        if not texts:
            return []

        comments_text = "\n".join(
            [f"{i + 1}. {text[:300]}" for i, text in enumerate(texts)]
        )
        format_lines = "\n".join([f"{i + 1}:category" for i in range(len(texts))])

        prompt = f"""Classify the toxicity of each comment.

COMMENTS:
{comments_text}

CATEGORIES:
- toxic (insults, profanity, threats)
- friendly (gratitude, praise)
- neutral (neutral)

Response format (strict):
{format_lines}

Example:
1:toxic
2:neutral
3:friendly

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

                    category_text = parts[1].strip().lower()

                    if "toxic" in category_text:
                        results.append("toxic")
                    elif "friendly" in category_text or "friend" in category_text:
                        results.append("friendly")
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
        Analyze toxicity of all comments.

        Args:
            comments: list of comment dicts

        Returns:
            dict with analysis results
        """
        print("Analyzing toxicity via LLM...")

        toxicity_by_comment = {}
        toxicity_by_user = defaultdict(list)
        failed_batches = []

        pbar = tqdm(
            total=len(comments),
            desc="Toxicity",
            unit="comm",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )

        for i in range(0, len(comments), self.batch_size):
            batch = comments[i : i + self.batch_size]
            texts = [comment.get("text", "") or "" for comment in batch]

            toxicities = self._analyze_text_with_llm(texts)

            if len(toxicities) != len(texts):
                print(
                    f"\n⚠ Batch error: got {len(toxicities)} results instead of {len(texts)}"
                )
                failed_batches.append((batch, texts))
                toxicities = ["neutral"] * len(texts)

            for comment, toxicity in zip(batch, toxicities):
                comment_id = comment["comment_id"]
                user_id = comment["user"]["id"]
                toxicity_by_comment[comment_id] = toxicity
                toxicity_by_user[user_id].append(toxicity)

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
                toxicities = self._analyze_text_with_llm(texts)

                if len(toxicities) == len(texts):
                    for comment, toxicity in zip(batch, toxicities):
                        comment_id = comment["comment_id"]
                        user_id = comment["user"]["id"]
                        toxicity_by_comment[comment_id] = toxicity
                        toxicity_by_user[user_id] = [
                            t for t in toxicity_by_user[user_id] if t != "neutral"
                        ] + [toxicity]
                else:
                    print(f"\n⚠ Batch failed again: {len(toxicities)}/{len(texts)}")

                retry_pbar.update(1)
                time.sleep(0.2)

            retry_pbar.close()

        print(f"✓ Analyzed {len(comments)} comments")

        # Aggregate per-user stats
        users_toxicity_stats = {}
        for user_id, toxicities in toxicity_by_user.items():
            counter = Counter(toxicities)
            total = len(toxicities)
            dominant_category = counter.most_common(1)[0][0]

            users_toxicity_stats[user_id] = {
                "dominant": dominant_category,
                "toxic_count": counter["toxic"],
                "neutral_count": counter["neutral"],
                "friendly_count": counter["friendly"],
                "total": total,
            }

        return {
            "comments_toxicity": toxicity_by_comment,
            "users_toxicity": users_toxicity_stats,
            "total_stats": self._calculate_total_stats(
                toxicity_by_comment, users_toxicity_stats
            ),
        }

    def _calculate_total_stats(
        self, comments_toxicity: Dict, users_toxicity: Dict
    ) -> Dict:
        """Calculate aggregate statistics."""
        comments_counter = Counter(comments_toxicity.values())
        users_categories = [
            user_data["dominant"] for user_data in users_toxicity.values()
        ]
        users_counter = Counter(users_categories)

        return {
            "comments": {
                "toxic": comments_counter["toxic"],
                "neutral": comments_counter["neutral"],
                "friendly": comments_counter["friendly"],
                "total": len(comments_toxicity),
            },
            "users": {
                "toxic": users_counter["toxic"],
                "neutral": users_counter["neutral"],
                "friendly": users_counter["friendly"],
                "total": len(users_toxicity),
            },
        }

    def print_toxicity_stats(self, results: Dict):
        """Print toxicity statistics to console."""
        stats = results["total_stats"]

        print("\nComment statistics:")
        print(
            f"  • Toxic:    {stats['comments']['toxic']} ({stats['comments']['toxic'] / stats['comments']['total'] * 100:.1f}%)"
        )
        print(
            f"  • Neutral:  {stats['comments']['neutral']} ({stats['comments']['neutral'] / stats['comments']['total'] * 100:.1f}%)"
        )
        print(
            f"  • Friendly: {stats['comments']['friendly']} ({stats['comments']['friendly'] / stats['comments']['total'] * 100:.1f}%)"
        )

        print("\nUser statistics:")
        print(
            f"  • Predominantly toxic:    {stats['users']['toxic']} ({stats['users']['toxic'] / stats['users']['total'] * 100:.1f}%)"
        )
        print(
            f"  • Predominantly neutral:  {stats['users']['neutral']} ({stats['users']['neutral'] / stats['users']['total'] * 100:.1f}%)"
        )
        print(
            f"  • Predominantly friendly: {stats['users']['friendly']} ({stats['users']['friendly'] / stats['users']['total'] * 100:.1f}%)"
        )
