"""Company/ticker mapping engine (Step 4)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process
from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import ArticleTicker, NewsArticle, get_db_session

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 75


@dataclass
class TickerMatch:
    ticker: str
    company_name: str
    match_score: float
    matched_text: str


@lru_cache
def _load_aliases() -> dict:
    path = get_settings().project_root / "data" / "ticker_aliases.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_search_index() -> list[tuple[str, str, str]]:
    """Returns list of (search_term, ticker, company_name)."""
    aliases = _load_aliases()
    index: list[tuple[str, str, str]] = []
    for ticker, info in aliases.items():
        company = info.get("company", ticker)
        index.append((company.lower(), ticker, company))
        index.append((ticker.lower(), ticker, company))
        for alias in info.get("aliases", []):
            index.append((alias.lower(), ticker, company))
    return index


@lru_cache
def _get_nlp():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except (OSError, ImportError):
        logger.warning("spaCy unavailable. Run: pip install spacy && python scripts/download_spacy.py")
        return None


def _fuzzy_match(text: str, index: list[tuple[str, str, str]]) -> list[TickerMatch]:
    choices = [item[0] for item in index]
    results = process.extract(
        text.lower(),
        choices,
        scorer=fuzz.partial_ratio,
        limit=3,
    )
    matches: list[TickerMatch] = []
    seen: set[str] = set()
    for choice, score, idx in results:
        if score < MATCH_THRESHOLD:
            continue
        _, ticker, company = index[idx]
        if ticker in seen:
            continue
        seen.add(ticker)
        matches.append(
            TickerMatch(
                ticker=ticker,
                company_name=company,
                match_score=float(score),
                matched_text=choice,
            )
        )
    return matches


def extract_entities(text: str) -> list[str]:
    nlp = _get_nlp()
    if nlp is None:
        return []
    doc = nlp(text[:5000])
    entities = []
    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT", "GPE"):
            entities.append(ent.text)
    return entities


def map_text_to_tickers(text: str) -> list[TickerMatch]:
    index = _build_search_index()
    matches: list[TickerMatch] = []
    seen: set[str] = set()

    for entity in extract_entities(text):
        for m in _fuzzy_match(entity, index):
            if m.ticker not in seen:
                seen.add(m.ticker)
                matches.append(m)

    aliases = _load_aliases()
    upper_tokens = set(re.findall(r"\b[A-Z]{2,12}\b", text))
    for token in upper_tokens:
        if token in aliases and token not in seen:
            info = aliases[token]
            seen.add(token)
            matches.append(
                TickerMatch(
                    ticker=token,
                    company_name=info.get("company", token),
                    match_score=100.0,
                    matched_text=token,
                )
            )

    for m in _fuzzy_match(text[:2000], index):
        if m.ticker not in seen:
            seen.add(m.ticker)
            matches.append(m)

    return sorted(matches, key=lambda x: x.match_score, reverse=True)


def map_article_tickers(
    article: NewsArticle,
    session: Optional[Session] = None,
) -> list[TickerMatch]:
    text = f"{article.title} {article.summary or article.cleaned_text or ''}"
    matches = map_text_to_tickers(text)

    def _persist(sess: Session) -> list[TickerMatch]:
        for m in matches:
            existing = (
                sess.query(ArticleTicker)
                .filter(
                    ArticleTicker.article_id == article.id,
                    ArticleTicker.ticker == m.ticker,
                )
                .first()
            )
            if existing:
                continue
            sess.add(
                ArticleTicker(
                    article_id=article.id,
                    ticker=m.ticker,
                    company_name=m.company_name,
                    match_score=m.match_score,
                )
            )
        return matches

    if session is not None:
        return _persist(session)

    with get_db_session() as sess:
        article_ref = sess.merge(article)
        return _persist(sess)


def map_all_recent_articles(limit: int = 50) -> dict[str, list[str]]:
    """Map tickers for recent articles without mappings."""
    result: dict[str, list[str]] = {}
    with get_db_session() as session:
        articles = (
            session.query(NewsArticle)
            .filter(NewsArticle.is_spam == False)  # noqa: E712
            .order_by(NewsArticle.created_at.desc())
            .limit(limit)
            .all()
        )
        for article in articles:
            matches = map_article_tickers(article, session=session)
            if matches:
                result[article.title[:50]] = [m.ticker for m in matches]
    return result
