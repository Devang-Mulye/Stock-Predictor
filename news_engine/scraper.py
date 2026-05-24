"""News scraping orchestration (Step 1)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

from config.settings import get_settings
from news_engine.sources import NEWS_SOURCES, NewsSource

logger = logging.getLogger(__name__)


@dataclass
class RawArticle:
    url: str
    title: str
    source: str
    source_credibility: float
    published_at: Optional[datetime]
    raw_text: str


def _parse_rss_date(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed"):
        if getattr(entry, key, None):
            try:
                return datetime(*entry[key][:6])
            except (TypeError, ValueError):
                pass
    if hasattr(entry, "published") and entry.published:
        try:
            return parsedate_to_datetime(entry.published)
        except (TypeError, ValueError):
            pass
    return None


def fetch_rss(source: NewsSource, client: httpx.Client) -> list[RawArticle]:
    articles: list[RawArticle] = []
    try:
        response = client.get(source.url, timeout=30.0)
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        for entry in feed.entries[:25]:
            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "").strip()
            if not link or not title:
                continue
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            if summary:
                soup = BeautifulSoup(summary, "lxml")
                text = soup.get_text(separator=" ", strip=True)
            else:
                text = title
            articles.append(
                RawArticle(
                    url=link,
                    title=title,
                    source=source.name,
                    source_credibility=source.credibility,
                    published_at=_parse_rss_date(entry),
                    raw_text=text,
                )
            )
    except Exception as exc:
        logger.warning("RSS fetch failed for %s: %s", source.name, exc)
    return articles


def fetch_html_listing(source: NewsSource, client: httpx.Client) -> list[RawArticle]:
    articles: list[RawArticle] = []
    try:
        response = client.get(source.url, timeout=30.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for link in soup.select("a[href]")[:30]:
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if not title or len(title) < 20:
                continue
            if not href.startswith("http"):
                continue
            articles.append(
                RawArticle(
                    url=href,
                    title=title,
                    source=source.name,
                    source_credibility=source.credibility,
                    published_at=None,
                    raw_text=title,
                )
            )
    except Exception as exc:
        logger.warning("HTML fetch failed for %s: %s", source.name, exc)
    return articles


def scrape_source(source: NewsSource, client: httpx.Client) -> list[RawArticle]:
    if source.source_type == "rss":
        return fetch_rss(source, client)
    return fetch_html_listing(source, client)


def scrape_all_sources(sources: Optional[list[NewsSource]] = None) -> list[RawArticle]:
    settings = get_settings()
    sources = sources or NEWS_SOURCES
    all_articles: list[RawArticle] = []
    headers = {"User-Agent": settings.user_agent}

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for source in sources:
            logger.info("Fetching news from %s", source.name)
            articles = scrape_source(source, client)
            all_articles.extend(articles)
            time.sleep(settings.request_delay_seconds)

    logger.info("Fetched %d raw articles", len(all_articles))
    return all_articles
