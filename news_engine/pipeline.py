"""News processing pipeline (Step 2)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from data.db import NewsArticle, get_db_session
from news_engine.scraper import RawArticle
from news_engine.sources import (
    BEARISH_KEYWORDS,
    BULLISH_KEYWORDS,
    SPAM_DOMAINS,
    SPAM_KEYWORDS,
)

logger = logging.getLogger(__name__)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.lower().strip())


def title_hash(title: str) -> str:
    return hashlib.sha256(_normalize_title(title).encode()).hexdigest()


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_keywords(text: str) -> tuple[list[str], list[str]]:
    lower = text.lower()
    bullish = [kw for kw in BULLISH_KEYWORDS if kw in lower]
    bearish = [kw for kw in BEARISH_KEYWORDS if kw in lower]
    return bullish, bearish


def is_spam(article: RawArticle, cleaned: str) -> bool:
    lower = (article.title + " " + cleaned).lower()
    if any(kw in lower for kw in SPAM_KEYWORDS):
        return True
    if any(domain in article.url.lower() for domain in SPAM_DOMAINS):
        return True
    return False


def summarize(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    parts = text.split(". ")
    summary_parts = []
    total = 0
    for part in parts:
        if total + len(part) > max_chars:
            break
        summary_parts.append(part)
        total += len(part) + 2
    summary = ". ".join(summary_parts)
    return summary if summary else text[:max_chars] + "..."


def _url_exists(session: Session, url: str) -> bool:
    return session.query(NewsArticle.id).filter(NewsArticle.url == url).first() is not None


def _hash_exists(session: Session, thash: str) -> bool:
    return (
        session.query(NewsArticle.id).filter(NewsArticle.title_hash == thash).first()
        is not None
    )


def process_articles(
    raw_articles: list[RawArticle],
    session: Optional[Session] = None,
) -> list[NewsArticle]:
    """Dedupe, clean, keyword-detect, and persist articles."""
    saved: list[NewsArticle] = []

    def _process(sess: Session) -> list[NewsArticle]:
        for raw in raw_articles:
            thash = title_hash(raw.title)
            if _url_exists(sess, raw.url) or _hash_exists(sess, thash):
                continue

            cleaned = clean_text(raw.raw_text or raw.title)
            if is_spam(raw, cleaned):
                logger.debug("Spam filtered: %s", raw.title[:60])
                continue

            bullish, bearish = detect_keywords(raw.title + " " + cleaned)
            article = NewsArticle(
                url=raw.url,
                title=raw.title,
                source=raw.source,
                source_credibility=raw.source_credibility,
                published_at=raw.published_at or datetime.utcnow(),
                raw_text=raw.raw_text,
                cleaned_text=cleaned,
                summary=summarize(cleaned),
                title_hash=thash,
                bullish_keywords=",".join(bullish) if bullish else None,
                bearish_keywords=",".join(bearish) if bearish else None,
                is_spam=False,
            )
            sess.add(article)
            saved.append(article)

        if saved:
            sess.flush()
        logger.info("Persisted %d new articles", len(saved))
        return saved

    if session is not None:
        return _process(session)

    with get_db_session() as sess:
        return _process(sess)
