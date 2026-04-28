"""Email notifier — sends the daily AI news briefing via SMTP."""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

from scraper import Article


# ── HTML template ────────────────────────────────────────────────────────────

_IMPORTANCE_COLOR = {
    range(9, 11): "#e74c3c",  # 9-10 → red
    range(7, 9):  "#e67e22",  # 7-8  → orange
    range(0, 7):  "#2ecc71",  # 0-6  → green
}


def _importance_color(score: int) -> str:
    for rng, color in _IMPORTANCE_COLOR.items():
        if score in rng:
            return color
    return "#95a5a6"


def _tag_badges(tags: list[str]) -> str:
    return "".join(
        f'<span style="display:inline-block;background:#eaf3ff;color:#2962ff;'
        f'border-radius:4px;padding:1px 7px;font-size:11px;margin:0 3px 3px 0;">'
        f"{t}</span>"
        for t in tags
    )


def _article_row(a: Article) -> str:
    color = _importance_color(a.importance_score)
    pub = a.published.strftime("%m/%d %H:%M") if a.published else ""
    summary = a.ai_summary or a.summary or "(요약 없음)"
    return f"""
    <tr>
      <td style="padding:14px 16px;border-bottom:1px solid #f0f0f0;vertical-align:top;">
        <div style="display:flex;align-items:flex-start;gap:10px;">
          <div style="min-width:32px;height:32px;border-radius:50%;background:{color};
                      color:#fff;font-weight:700;font-size:14px;display:flex;
                      align-items:center;justify-content:center;flex-shrink:0;">
            {a.importance_score}
          </div>
          <div style="flex:1;">
            <a href="{a.url}" style="color:#1a1a2e;font-weight:600;font-size:15px;
                                     text-decoration:none;line-height:1.4;">
              {a.title}
            </a>
            <div style="color:#888;font-size:12px;margin:3px 0;">
              {a.source} &nbsp;·&nbsp; {pub}
            </div>
            <div style="color:#444;font-size:13px;margin:5px 0 6px;">{summary}</div>
            <div>{_tag_badges(a.tags)}</div>
          </div>
        </div>
      </td>
    </tr>"""


def build_html(articles: list[Article], date_str: str) -> str:
    rows = "".join(_article_row(a) for a in articles[:30])
    total = len(articles)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 뉴스 브리핑 {date_str}</title></head>
<body style="margin:0;padding:0;background:#f5f6fa;font-family:'Apple SD Gothic Neo',
             'Noto Sans KR',sans-serif;">
  <div style="max-width:700px;margin:30px auto;background:#fff;border-radius:12px;
              box-shadow:0 2px 16px rgba(0,0,0,.08);overflow:hidden;">
    <!-- header -->
    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                padding:28px 24px;color:#fff;">
      <div style="font-size:22px;font-weight:700;">🤖 AI 뉴스 브리핑</div>
      <div style="font-size:14px;opacity:.85;margin-top:4px;">{date_str} &nbsp;·&nbsp; 총 {total}건</div>
    </div>
    <!-- legend -->
    <div style="padding:12px 20px;background:#fafafa;border-bottom:1px solid #eee;
                font-size:12px;color:#888;">
      중요도: &nbsp;
      <span style="color:#e74c3c;">●</span> 9–10 최고 &nbsp;
      <span style="color:#e67e22;">●</span> 7–8 높음 &nbsp;
      <span style="color:#2ecc71;">●</span> 1–6 보통
    </div>
    <!-- articles -->
    <table width="100%" cellpadding="0" cellspacing="0">
      <tbody>{rows}</tbody>
    </table>
    <!-- footer -->
    <div style="padding:18px 24px;background:#f5f6fa;text-align:center;
                font-size:12px;color:#aaa;">
      AI 뉴스 에이전트 · Powered by Claude &amp; RSS
    </div>
  </div>
</body>
</html>"""


def build_plain(articles: list[Article], date_str: str) -> str:
    lines = [f"AI 뉴스 브리핑 — {date_str}", "=" * 50, ""]
    for i, a in enumerate(articles[:30], 1):
        lines.append(f"[{i}] [{a.importance_score}/10] {a.title}")
        lines.append(f"     출처: {a.source}")
        lines.append(f"     링크: {a.url}")
        if a.ai_summary:
            lines.append(f"     요약: {a.ai_summary}")
        lines.append("")
    return "\n".join(lines)


# ── Send ─────────────────────────────────────────────────────────────────────

def send_email(
    articles: list[Article],
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    sender: str,
    recipients: list[str],
    use_tls: bool = True,
) -> None:
    date_str = datetime.now().strftime("%Y년 %m월 %d일")
    subject = f"🤖 AI 뉴스 브리핑 — {date_str} ({len(articles)}건)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(build_plain(articles, date_str), "plain", "utf-8"))
    msg.attach(MIMEText(build_html(articles, date_str), "html", "utf-8"))

    context = ssl.create_default_context()
    if use_tls:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(sender, recipients, msg.as_bytes())
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(sender, recipients, msg.as_bytes())

    print(f"[notifier] Email sent to {recipients} ({len(articles)} articles)")
