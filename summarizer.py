"""Gemini-powered news summarizer (REST API, no SDK needed)."""
import os
import json
import re
import requests
from scraper import Article

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

SYSTEM_PROMPT = """You are an AI news analyst. Analyze the given AI news articles and return a JSON array.

For each article assign an importance score 1-10 based on industry impact, novelty, and relevance.

Return ONLY a JSON array, no other text:
[
  {
    "title": "original title",
    "url": "article url",
    "importance_score": <1-10>,
    "korean_summary": "2-3 sentence Korean summary",
    "tags": ["tag1", "tag2"]
  }
]

Sort by importance_score descending."""


def summarize_articles(articles: list[Article]) -> list[Article]:
    if not articles:
        return []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[summarizer] GEMINI_API_KEY not set — skipping summarization")
        return articles

    article_texts = []
    for i, a in enumerate(articles, 1):
        article_texts.append(
            f"[{i}] Title: {a.title}\n"
            f"    Source: {a.source}\n"
            f"    URL: {a.url}\n"
            f"    Excerpt: {a.summary[:300] if a.summary else '(no excerpt)'}"
        )

    user_content = SYSTEM_PROMPT + "\n\nAnalyze these AI news articles:\n\n" + "\n\n".join(article_texts)

    payload = {
        "contents": [{"parts": [{"text": user_content}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[summarizer] Gemini API error: {e}")
        return articles

    raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[summarizer] JSON parse error: {e}")
        return articles

    url_map = {a.url: a for a in articles}
    enriched: list[Article] = []
    for item in items:
        url = item.get("url", "")
        art = url_map.get(url)
        if art is None:
            title = item.get("title", "")
            art = next((a for a in articles if a.title == title), None)
        if art is None:
            continue
        art.ai_summary = item.get("korean_summary", "")
        art.importance_score = int(item.get("importance_score", 0))
        art.tags = item.get("tags", art.tags)
        enriched.append(art)

    returned_urls = {a.url for a in enriched}
    for a in articles:
        if a.url not in returned_urls:
            enriched.append(a)

    enriched.sort(key=lambda a: a.importance_score, reverse=True)
    return enriched
