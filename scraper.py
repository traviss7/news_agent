"""AI news scraper — Google News RSS (server-friendly)."""
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Optional

FEEDS = [
    {"name": "Google News – AI", "url": "https://news.google.com/rss/search?q=artificial+intelligence&hl=en&gl=US&ceid=US:en", "tag": "AI"},
    {"name": "Google News – LLM", "url": "https://news.google.com/rss/search?q=LLM+large+language+model&hl=en&gl=US&ceid=US:en", "tag": "LLM"},
    {"name": "Google News – OpenAI", "url": "https://news.google.com/rss/search?q=OpenAI+ChatGPT&hl=en&gl=US&ceid=US:en", "tag": "OpenAI"},
    {"name": "Google News – Gemini", "url": "https://news.google.com/rss/search?q=Google+Gemini+AI&hl=en&gl=US&ceid=US:en", "tag": "Google"},
    {"name": "Google News – Claude", "url": "https://news.google.com/rss/search?q=Anthropic+Claude+AI&hl=en&gl=US&ceid=US:en", "tag": "Anthropic"},
    {"name": "Google News – AI Research", "url": "https://news.google.com/rss/search?q=AI+research+paper+2025&hl=en&gl=US&ceid=US:en", "tag": "Research"},
    {"name": "Google News – AI 한국", "url": "https://news.google.com/rss/search?q=인공지능+AI&hl=ko&gl=KR&ceid=KR:ko", "tag": "국내"},
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


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())[:500]


def _parse_date(text: Optional[str]) -> Optional[datetime]:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).astimezone(timezone.utc)
    except Exception:
        return None


def _parse_feed(content: bytes, source: str, tag: str,
                cutoff: datetime, max_count: int) -> list[Article]:
    articles = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    channel = root.find("channel") or root
    items = channel.findall("item")
    seen_titles = set()

    for item in items:
        if len(articles) >= max_count:
            break

        title_el = item.find("title")
        title = (title_el.text or "").strip() if title_el is not None else "(no title)"
        # Google News prepends "source - " to titles, clean it up
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()

        if title in seen_titles:
            continue
        seen_titles.add(title)

        link_el = item.find("link")
        url = (link_el.text or "").strip() if link_el is not None else ""

        pub_el = item.find("pubDate")
        pub = _parse_date(pub_el.text if pub_el is not None else None)
        if pub and pub < cutoff:
            continue

        desc_el = item.find("description")
        summary = _strip_html(desc_el.text or "") if desc_el is not None else ""

        articles.append(Article(
            title=title, url=url, source=source,
            published=pub, summary=summary, tags=[tag]
        ))

    return articles


def fetch_articles(hours_back: int = 24, max_per_feed: int = 10) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"}
    all_articles: list[Article] = []

    for feed in FEEDS:
        try:
            resp = requests.get(feed["url"], headers=headers, timeout=15)
            resp.raise_for_status()
            arts = _parse_feed(resp.content, feed["name"], feed["tag"],
                               cutoff, max_per_feed)
            print(f"[scraper] {feed['name']}: {len(arts)}건")
            all_articles.extend(arts)
        except Exception as e:
            print(f"[scraper] 실패 {feed['name']}: {e}")

    return all_articles
