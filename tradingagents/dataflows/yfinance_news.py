"""yfinance-based news data fetching functions."""

import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta

from .stockstats_utils import yf_retry
from .vnstock_news_fetch import get_vnstock_news_section


def _extract_article_data(article: dict) -> dict:
    """Extract article data from yfinance news format (handles nested 'content' structure)."""
    # Handle nested content structure
    if "content" in article:
        content = article["content"]
        title = content.get("title", "No title")
        summary = content.get("summary", "")
        provider = content.get("provider", {})
        publisher = provider.get("displayName", "Unknown")

        # Get URL from canonicalUrl or clickThroughUrl
        url_obj = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
        link = url_obj.get("url", "")

        # Get publish date
        pub_date_str = content.get("pubDate", "")
        pub_date = None
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return {
            "title": title,
            "summary": summary,
            "publisher": publisher,
            "link": link,
            "pub_date": pub_date,
        }
    else:
        # Fallback for flat structure
        return {
            "title": article.get("title", "No title"),
            "summary": article.get("summary", ""),
            "publisher": article.get("publisher", "Unknown"),
            "link": article.get("link", ""),
            "pub_date": None,
        }


def _fetch_yahoo_finance_news_body(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Returns filtered Yahoo Finance article text, or empty string if none in range,
    or a line starting with 'Error' on failure.
    """
    try:
        stock = yf.Ticker(ticker)
        news = yf_retry(lambda: stock.get_news(count=20))

        if not news:
            return ""

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        news_str = ""
        filtered_count = 0

        for article in news:
            data = _extract_article_data(article)

            if data["pub_date"]:
                pub_date_naive = data["pub_date"].replace(tzinfo=None)
                if not (start_dt <= pub_date_naive <= end_dt + relativedelta(days=1)):
                    continue

            news_str += f"### {data['title']} (source: {data['publisher']})\n"
            if data["summary"]:
                news_str += f"{data['summary']}\n"
            if data["link"]:
                news_str += f"Link: {data['link']}\n"
            news_str += "\n"
            filtered_count += 1

        if filtered_count == 0:
            return ""

        return news_str

    except Exception as e:
        return f"Error fetching Yahoo Finance news: {e}"


def get_news_yfinance(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Retrieve news for a specific stock ticker using yfinance.
    For tickers ending in .VN, also appends Vietnamese RSS headlines via vnstock_news
    (optional install) mentioning the symbol.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "VHM.VN")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted string containing news articles
    """
    ticker = ticker.strip()
    header = f"## {ticker} News, from {start_date} to {end_date}:\n\n"

    yahoo_body = _fetch_yahoo_finance_news_body(ticker, start_date, end_date)

    if yahoo_body.startswith("Error"):
        yahoo_block = yahoo_body + "\n"
    elif yahoo_body:
        yahoo_block = yahoo_body
    else:
        yahoo_block = (
            f"No Yahoo Finance articles for {ticker} between {start_date} and {end_date} "
            "(or none with publish dates in range).\n"
        )

    parts = [
        header,
        "### Yahoo Finance\n",
        yahoo_block,
        "\n",
    ]

    if ticker.upper().endswith(".VN"):
        symbol_base = ticker.upper().removesuffix(".VN").strip()
        vn_body = (
            get_vnstock_news_section(symbol_base, start_date, end_date)
            if symbol_base
            else ""
        )
        parts.append("### Vietnamese media (vnstock_news)\n")
        if vn_body:
            parts.append(vn_body)
        else:
            parts.append(
                "No matching Vietnamese RSS articles in this range, or feeds returned no data.\n"
            )

    return "".join(parts)


def get_global_news_yfinance(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    Retrieve global/macro economic news using yfinance Search.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted string containing global news articles
    """
    # Search queries for macro/global news
    search_queries = [
        "stock market economy",
        "Federal Reserve interest rates",
        "inflation economic outlook",
        "global markets trading",
    ]

    all_news = []
    seen_titles = set()

    try:
        for query in search_queries:
            search = yf_retry(lambda q=query: yf.Search(
                query=q,
                news_count=limit,
                enable_fuzzy_query=True,
            ))

            if search.news:
                for article in search.news:
                    # Handle both flat and nested structures
                    if "content" in article:
                        data = _extract_article_data(article)
                        title = data["title"]
                    else:
                        title = article.get("title", "")

                    # Deduplicate by title
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append(article)

            if len(all_news) >= limit:
                break

        if not all_news:
            return f"No global news found for {curr_date}"

        # Calculate date range
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        news_str = ""
        for article in all_news[:limit]:
            # Handle both flat and nested structures
            if "content" in article:
                data = _extract_article_data(article)
                # Skip articles published after curr_date (look-ahead guard)
                if data.get("pub_date"):
                    pub_naive = data["pub_date"].replace(tzinfo=None) if hasattr(data["pub_date"], "replace") else data["pub_date"]
                    if pub_naive > curr_dt + relativedelta(days=1):
                        continue
                title = data["title"]
                publisher = data["publisher"]
                link = data["link"]
                summary = data["summary"]
            else:
                title = article.get("title", "No title")
                publisher = article.get("publisher", "Unknown")
                link = article.get("link", "")
                summary = ""

            news_str += f"### {title} (source: {publisher})\n"
            if summary:
                news_str += f"{summary}\n"
            if link:
                news_str += f"Link: {link}\n"
            news_str += "\n"

        return f"## Global Market News, from {start_date} to {curr_date}:\n\n{news_str}"

    except Exception as e:
        return f"Error fetching global news: {str(e)}"
