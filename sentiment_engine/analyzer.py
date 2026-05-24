"""Financial sentiment analysis with FinBERT (Step 3)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import get_settings
from data.db import NewsArticle, get_db_session

logger = logging.getLogger(__name__)

LABEL_MAP = {
    "positive": "Positive",
    "negative": "Negative",
    "neutral": "Neutral",
}


@dataclass
class SentimentResult:
    label: str
    score: float
    confidence: float


class SentimentAnalyzer:
    def __init__(self):
        self._pipeline = None
        self._settings = get_settings()

    def _load_model(self):
        if self._pipeline is not None:
            return
        try:
            from transformers import pipeline

            cache_dir = str(self._settings.models_cache_dir)
            self._settings.models_cache_dir.mkdir(parents=True, exist_ok=True)
            device = -1 if self._settings.use_cpu_only else 0
            try:
                import torch

                if not torch.cuda.is_available():
                    device = -1
            except ImportError:
                device = -1

            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self._settings.finbert_model_id,
                tokenizer=self._settings.finbert_model_id,
                device=device,
                model_kwargs={"cache_dir": cache_dir},
            )
            logger.info("Loaded FinBERT model: %s", self._settings.finbert_model_id)
        except Exception as exc:
            logger.error("Failed to load FinBERT: %s", exc)
            raise

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult("Neutral", 0.0, 0.0)

        self._load_model()
        truncated = text[:512]
        result = self._pipeline(truncated)[0]
        raw_label = result["label"].lower()
        label = LABEL_MAP.get(raw_label, result["label"])
        score = float(result["score"])
        if "neg" in raw_label:
            signed_score = -score
        elif "pos" in raw_label:
            signed_score = score
        else:
            signed_score = 0.0
        return SentimentResult(label=label, score=signed_score, confidence=score * 100)

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [self.analyze(t) for t in texts]


@lru_cache
def get_analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()


def analyze_article(article: NewsArticle, analyzer: Optional[SentimentAnalyzer] = None) -> SentimentResult:
    analyzer = analyzer or get_analyzer()
    text = f"{article.title}. {article.summary or article.cleaned_text or ''}"
    return analyzer.analyze(text)


def analyze_and_persist(
    articles: Optional[list[NewsArticle]] = None,
    session: Optional[Session] = None,
) -> int:
    """Run sentiment on articles missing scores."""

    def _run(sess: Session) -> int:
        analyzer = get_analyzer()
        if articles is not None:
            to_process = [a for a in articles if a.sentiment_label is None]
        else:
            to_process = (
                sess.query(NewsArticle)
                .filter(
                    NewsArticle.is_spam == False,  # noqa: E712
                    NewsArticle.sentiment_label.is_(None),
                )
                .order_by(NewsArticle.created_at.desc())
                .limit(100)
                .all()
            )
        count = 0
        for article in to_process:
            try:
                result = analyze_article(article, analyzer)
                article.sentiment_label = result.label
                article.sentiment_score = result.score
                article.sentiment_confidence = result.confidence
                count += 1
            except Exception as exc:
                logger.warning("Sentiment failed for article %s: %s", article.id, exc)
        return count

    if session is not None:
        return _run(session)

    with get_db_session() as sess:
        return _run(sess)
