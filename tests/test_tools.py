"""Smoke tests for the SEO tools.

These tests hit the real network for the free tools. They are intentionally
small and cheap. Run with:  python -m pytest tests/ -q
"""
from __future__ import annotations

import os
import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.web_search import duckduckgo_search
from tools.web_fetch import fetch_url, extract_visible_text, extract_all_links
from tools.onpage_audit import onpage_audit
from tools.schema_extract import extract_structured_data
from tools.sitemap_robots import fetch_robots_txt
from tools.rank_tracker import estimate_keyword_rank


TEST_URL = os.getenv("TEST_URL", "https://example.com/")


class TestSEOTools(unittest.TestCase):
    def test_duckduckgo_search(self):
        out = duckduckgo_search.invoke({"query": "site:example.com", "max_results": 3})
        self.assertIsInstance(out, list)

    def test_fetch_url(self):
        out = fetch_url.invoke({"url": TEST_URL})
        self.assertTrue(out.get("ok"), msg=out)
        self.assertIn("html", out)

    def test_extract_visible_text(self):
        out = extract_visible_text.invoke({"url": TEST_URL, "max_chars": 1000})
        self.assertTrue(out.get("ok"))
        self.assertGreater(out["word_count"], 0)

    def test_extract_all_links(self):
        out = extract_all_links.invoke({"url": TEST_URL})
        self.assertTrue(out.get("ok"))
        self.assertIn("internal", out)
        self.assertIn("external", out)

    def test_onpage_audit(self):
        out = onpage_audit.invoke({"url": TEST_URL})
        self.assertTrue(out.get("ok"), msg=out)
        self.assertIn("title", out)
        self.assertIn("issues", out)

    def test_schema_extract(self):
        out = extract_structured_data.invoke({"url": TEST_URL})
        self.assertTrue(out.get("ok"), msg=out)
        self.assertIn("json_ld", out)

    def test_robots_txt(self):
        out = fetch_robots_txt.invoke({"domain_or_url": "https://example.com"})
        # example.com may 404 robots.txt, that's fine — we just need the call to succeed
        self.assertIn("url", out)

    def test_estimate_keyword_rank(self):
        out = estimate_keyword_rank.invoke(
            {"keyword": "example domain", "domain": "example.com", "depth": 10}
        )
        self.assertTrue(out.get("ok"))


if __name__ == "__main__":
    unittest.main()
