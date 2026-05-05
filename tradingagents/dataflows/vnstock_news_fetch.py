"""Vietnamese stock news via vnstock_news (optional dependency) for .VN tickers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta

# Finance-focused Vietnamese sources; RSS-only for speed.
_VN_NEWS_SITES = ("cafef", "vietstock", "vneconomy")


def _parse_publish_time(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    for candidate in (s, s.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2}(:\d{2})?)", s)
    if m:
        try:
            return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M")
            except ValueError:
                pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _symbol_mentions_text(symbol_base: str, title: str, desc: str) -> bool:
    text = f"{title or ''} {desc or ''}".strip()
    if not text:
        return False
    pat = re.compile(rf"\b{re.escape(symbol_base)}\b", re.IGNORECASE)
    return bool(pat.search(text))


def get_vnstock_news_section(
    symbol_base: str,
    start_date: str,
    end_date: str,
    limit_per_site: int = 20,
    max_total: int = 18,
) -> str:
    """
    Pull recent Vietnamese media headlines mentioning the ticker via vnstock_news RSS.

    symbol_base: e.g. "VHM" (no .VN suffix).
    Returns formatted markdown section body (no outer ##), or empty string if unavailable.
    """
    try:
        from vnstock_news import Crawler
    except ImportError:
        return (
            "(vnstock_news package not installed; pip install vnstock_news "
            "to enable Vietnamese news for .VN tickers.)"
        )

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + relativedelta(days=1)

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    lines: list[str] = []
    article_count = 0

    for site in _VN_NEWS_SITES:
        try:
            crawler = Crawler(site_name=site)
            articles = crawler.get_articles_from_feed(limit_per_feed=limit_per_site)
        except Exception:
            continue

        for art in articles or []:
            if article_count >= max_total:
                break
            url = (art.get("url") or "").strip()
            title = art.get("title") or ""
            desc = art.get("short_description") or art.get("description") or ""
            if not _symbol_mentions_text(symbol_base, title, desc):
                continue

            pub = _parse_publish_time(art.get("publish_time"))
            if pub is not None:
                if not (start_dt <= pub <= end_dt):
                    continue

            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            else:
                tkey = title.strip().lower()
                if tkey and tkey in seen_titles:
                    continue
                if tkey:
                    seen_titles.add(tkey)

            src = art.get("source") or site
            article_count += 1

            lines.append(f"### {title} (source: {src})\n")
            if desc:
                lines.append(f"{desc}\n")
            if url:
                lines.append(f"Link: {url}\n")
            lines.append("\n")

        if article_count >= max_total:
            break

    if not lines:
        return ""

    return "".join(lines).rstrip() + "\n"
