"""Claude-powered news summarizer with prompt caching."""
import anthropic
from scraper import Article

SYSTEM_PROMPT = """You are an AI news analyst. Your job is to analyze a list of AI-related news articles and produce a structured daily briefing in Korean.

For each article provided, assign an importance score from 1-10 based on:
- Impact on AI industry/research (higher = more impactful)
- Novelty and newsworthiness
- Relevance to practitioners and researchers

Then return a JSON array with the following structure for each article:
{
  "title": "original title",
  "source": "source name",
  "url": "article url",
  "importance_score": <1-10>,
  "korean_summary": "2-3 sentence Korean summary of the article",
  "tags": ["tag1", "tag2"]  // e.g. ["LLM", "연구", "산업", "규제", "오픈소스"]
}

Sort the array by importance_score descending.
Respond ONLY with the JSON array, no other text."""

client = anthropic.Anthropic()


def summarize_articles(articles: list[Article]) -> list[Article]:
    if not articles:
        return []

    # Build article list for the prompt
    article_texts = []
    for i, a in enumerate(articles, 1):
        article_texts.append(
            f"[{i}] Title: {a.title}\n"
            f"    Source: {a.source}\n"
            f"    URL: {a.url}\n"
            f"    Excerpt: {a.summary[:300] if a.summary else '(no excerpt)'}"
        )

    user_content = "Analyze the following AI news articles:\n\n" + "\n\n".join(article_texts)

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    import json, re

    raw = next((b.text for b in response.content if b.type == "text"), "[]")
    # strip possible markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[summarizer] JSON parse error: {e}")
        return articles

    # map back to Article objects
    url_map = {a.url: a for a in articles}
    enriched: list[Article] = []
    for item in items:
        url = item.get("url", "")
        art = url_map.get(url)
        if art is None:
            # fallback: match by title
            title = item.get("title", "")
            art = next((a for a in articles if a.title == title), None)
        if art is None:
            continue
        art.ai_summary = item.get("korean_summary", "")
        art.importance_score = int(item.get("importance_score", 0))
        art.tags = item.get("tags", art.tags)
        enriched.append(art)

    # articles not returned by Claude keep their defaults
    returned_urls = {a.url for a in enriched}
    for a in articles:
        if a.url not in returned_urls:
            enriched.append(a)

    enriched.sort(key=lambda a: a.importance_score, reverse=True)
    return enriched
