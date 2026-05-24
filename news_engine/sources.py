"""News source definitions (Step 1)."""

from dataclasses import dataclass, field
from typing import Literal

SourceType = Literal["rss", "html"]


@dataclass
class NewsSource:
    name: str
    url: str
    source_type: SourceType
    credibility: float = 0.7
    categories: list[str] = field(default_factory=list)


# Practical subset of README sources — RSS preferred for stability
NEWS_SOURCES: list[NewsSource] = [
    NewsSource(
        name="Moneycontrol",
        url="https://www.moneycontrol.com/rss/latestnews.xml",
        source_type="rss",
        credibility=0.85,
        categories=["markets", "stocks"],
    ),
    NewsSource(
        name="Economic Times Markets",
        url="https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        source_type="rss",
        credibility=0.9,
        categories=["markets"],
    ),
    NewsSource(
        name="LiveMint Markets",
        url="https://www.livemint.com/rss/markets",
        source_type="rss",
        credibility=0.85,
        categories=["markets"],
    ),
    NewsSource(
        name="Business Standard",
        url="https://www.business-standard.com/rss/markets-106.rss",
        source_type="rss",
        credibility=0.85,
        categories=["markets"],
    ),
    NewsSource(
        name="CNBC TV18",
        url="https://www.cnbctv18.com/rss/market.xml",
        source_type="rss",
        credibility=0.8,
        categories=["markets"],
    ),
    NewsSource(
        name="RBI Press Releases",
        url="https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
        source_type="html",
        credibility=0.95,
        categories=["policy", "macro"],
    ),
    NewsSource(
        name="SEBI Notifications",
        url="https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=1&smid=0",
        source_type="html",
        credibility=0.95,
        categories=["regulatory"],
    ),
]

BULLISH_KEYWORDS = [
    "awarded",
    "contract",
    "profit rise",
    "expansion",
    "acquisition",
    "approval",
    "partnership",
    "production increase",
    "investment",
    "capacity expansion",
    "buyback",
    "dividend",
    "upgrade",
    "record high",
    "order win",
]

BEARISH_KEYWORDS = [
    "investigation",
    "fraud",
    "decline",
    "loss",
    "debt",
    "downgrade",
    "bankruptcy",
    "weak guidance",
    "dilution",
    "regulatory action",
    "penalty",
    "default",
    "resignation",
    "probe",
]

SPAM_KEYWORDS = [
    "casino",
    "crypto giveaway",
    "100% guaranteed",
    "get rich quick",
    "click here to win",
]

SPAM_DOMAINS = [
    "bit.ly spam",
]
