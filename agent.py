"""Main AI news agent — scrape, summarize, and send."""
import os
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        log.error("Required environment variable %s is not set", name)
        sys.exit(1)
    return val


def run_once() -> None:
    """Execute one full scrape → summarize → send cycle."""
    log.info("=== AI News Agent starting ===")

    # ── imports inside the function so the scheduler module can be imported
    #    even before all deps are installed (for --help, etc.)
    from scraper import fetch_articles
    from summarizer import summarize_articles
    from notifier import send_email

    # Config
    hours_back = int(os.getenv("HOURS_BACK", "24"))
    max_per_feed = int(os.getenv("MAX_PER_FEED", "10"))
    min_importance = int(os.getenv("MIN_IMPORTANCE", "0"))

    smtp_host = _require("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = _require("SMTP_USER")
    smtp_password = _require("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_SENDER", smtp_user)
    recipients_raw = _require("EMAIL_RECIPIENTS")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    use_tls = os.getenv("SMTP_USE_SSL", "true").lower() != "false"

    # 1. Scrape
    log.info("Fetching articles (last %d hours)…", hours_back)
    articles = fetch_articles(hours_back=hours_back, max_per_feed=max_per_feed)
    log.info("Fetched %d articles", len(articles))

    if not articles:
        log.warning("No articles found — skipping email.")
        return

    # 2. Summarize with Claude
    log.info("Summarizing with Claude…")
    articles = summarize_articles(articles)
    log.info("Summarization complete")

    # 3. Filter by minimum importance
    if min_importance > 0:
        articles = [a for a in articles if a.importance_score >= min_importance]
        log.info("After filtering (>=%d): %d articles", min_importance, len(articles))

    if not articles:
        log.warning("All articles filtered out — skipping email.")
        return

    # 4. Send email
    log.info("Sending email to %s…", recipients)
    send_email(
        articles=articles,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        sender=sender,
        recipients=recipients,
        use_tls=use_tls,
    )
    log.info("=== Done ===")


def start_scheduler() -> None:
    """Start the APScheduler cron job and block forever."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    schedule_hour = int(os.getenv("SCHEDULE_HOUR", "8"))
    schedule_minute = int(os.getenv("SCHEDULE_MINUTE", "0"))
    timezone = os.getenv("TIMEZONE", "Asia/Seoul")

    scheduler = BlockingScheduler(timezone=timezone)
    scheduler.add_job(
        run_once,
        trigger=CronTrigger(hour=schedule_hour, minute=schedule_minute),
        id="ai_news_briefing",
        name="AI News Briefing",
        misfire_grace_time=600,  # 10-minute grace window
    )

    next_run = scheduler.get_job("ai_news_briefing").next_run_time
    log.info(
        "Scheduler started — will run daily at %02d:%02d (%s)",
        schedule_hour,
        schedule_minute,
        timezone,
    )
    log.info("Next run: %s", next_run)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI News Agent")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run immediately instead of waiting for the scheduled time",
    )
    args = parser.parse_args()

    if args.run_now:
        run_once()
    else:
        start_scheduler()
