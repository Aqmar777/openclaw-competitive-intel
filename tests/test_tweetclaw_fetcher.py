import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "tweetclaw_fetcher.py"
SPEC = importlib.util.spec_from_file_location("tweetclaw_fetcher", MODULE_PATH)
tweetclaw_fetcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tweetclaw_fetcher)


class TweetClawFetcherTests(unittest.TestCase):
    def test_extracts_top_level_tweets(self):
        body = {"tweets": [{"id": "1", "text": "hello"}]}

        self.assertEqual(tweetclaw_fetcher.extract_tweets(body), body["tweets"])

    def test_extracts_nested_tweets(self):
        body = {"data": {"tweets": [{"id": "2", "text": "nested"}]}}

        self.assertEqual(tweetclaw_fetcher.extract_tweets(body), body["data"]["tweets"])

    def test_normalizes_tweet_shape(self):
        tweet = {
            "id": "187",
            "text": "pricing changed",
            "createdAt": "2026-05-23T11:00:00Z",
            "author": {"userName": "competitor"},
            "likeCount": 4,
            "retweetCount": 2,
            "replyCount": 1,
            "quoteCount": 3,
        }

        self.assertEqual(
            tweetclaw_fetcher.normalize_tweet(tweet),
            {
                "id": "187",
                "title": "",
                "body": "pricing changed",
                "author": "competitor",
                "score": 10,
                "url": "https://x.com/i/status/187",
                "created_at": "2026-05-23T11:00:00Z",
                "comments": [],
            },
        )

    def test_builds_standard_contract(self):
        result = tweetclaw_fetcher.build_result(
            "openclaw",
            {
                "tweets": [{"id": "7", "text": "launch"}],
                "has_more": True,
                "next_cursor": "next",
            },
        )

        self.assertEqual(result["source"], "x_tweetclaw")
        self.assertEqual(result["source_id"], "openclaw")
        self.assertEqual(len(result["posts"]), 1)
        self.assertTrue(result["metadata"]["has_more"])
        self.assertEqual(result["metadata"]["next_cursor"], "next")


if __name__ == "__main__":
    unittest.main()
