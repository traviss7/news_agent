"""RSS-based AI news scraper."""
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import Optional

FEEDS = [
    {
        "name": "MIT Technology Review – AI",
        "url": "https://www.technologyreview.com/feed/",
        "tag": "MIT",
    },
    {
        "name": "The Verge – AI",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "tag": "Verge",
    },
    {
        "name": "VentureBeat – AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "tag": "VentureBeat",
    },
    {
        "name": "TechCrunch – AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "tag": "TechCrunch",
    },
    {
        "name": "Wired – AI",
        "url": "https://www.wired.com/feed/tag/ai/latest/rss",
        "tag": "Wired",
    },
    {
        "name": "Ars Technica – AI",
        "url": "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "tag": "Ars",
    },
    {
        "name": "Google DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "tag": "DeepMind",
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "tag": "OpenAI",
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/rss.xml",
        "tag": "Anthropic",
    },
    {
        "name": "HuggingFace Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "tag": "HuggingFace",
    },
]


@dataclass
class Article:
    title: str
    url: str
    source: str
    published: Optional[datetime]
    summary: str = ""
    ai_summary: str = ""
    importance_score: int = 0
    tags: list[str] = field(default_factory=list)


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _entry_summary(entry) -> str:
    for attr in ("summary", "description", "content"):
        val = getattr(entry, attr, None)
        if val:
            if isinstance(val, list):
                val = val[0].get("value", "")
            # strip HTML tags simply
            import re
            val = re.sub(r"<[^>]+>", " ", str(val))
            val = " ".join(val.split())
            return val[:500]
    return ""


def fetch_articles(hours_back: int = 24, max_per_feed: int = 10) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    articles: list[Article] = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"}

    for feed_info in FEEDS:
        try:
            resp = requests.get(feed_info["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"[scraper] Failed to fetch {feed_info['name']}: {e}")
            continue

        count = 0
        for entry in feed.entries:
            if count >= max_per_feed:
                break
            pub = _parse_date(entry)
            # include articles without a date, or those within the window
            if pub and pub < cutoff:
                continue
            article = Article(
                title=getattr(entry, "title", "(no title)").strip(),
                url=getattr(entry, "link", ""),
                source=feed_info["name"],
                published=pub,
                summary=_entry_summary(entry),
                tags=[feed_info["tag"]],
            )
            articles.append(article)
            count += 1

    return articles
