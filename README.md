# Local AI-Powered Indian Stock Market Trading System
## Master Architecture + Prompt Specification

---

# Objective

Build a fully local AI-powered Indian stock market analysis and recommendation system that:

- Continuously monitors Indian stock market news
- Fetches live and historical market data
- Tracks technical indicators and chart patterns
- Uses financial sentiment analysis on news and announcements
- Uses LLM reasoning to analyze signals
- Suggests:
  - Which stock to buy
  - Suggested entry price
  - Suggested stop loss
  - Suggested target
  - Confidence level
  - Risk level
- Sends alerts via Telegram/Discord/Web Dashboard
- Stores historical predictions and evaluates performance
- Operates primarily using FREE or open-source tools/models
- Runs LOCALLY using consumer hardware

This system is NOT intended initially for fully automated trading execution.
It is intended to be an AI-assisted trading advisor.

---

# IMPORTANT REALITY CHECK

## Financial Expectations

The system should optimize for:

- Consistent profitability
- Risk management
- Controlled losses
- Long-term compounding

DO NOT optimize solely for:

- Maximum profit
- Aggressive leverage
- High-frequency gambling behavior

### Risk Constraints

Current capital:
- ₹30,000

Weekly maximum allowed drawdown:
- ₹5,000

Desired monthly return target:
- 5% to 10%

System must prioritize:
- capital preservation
- probability-weighted trades
- risk-adjusted returns

---

# SYSTEM OVERVIEW

The architecture should include the following components:

```text
News Sources
    ↓
News Processing Pipeline
    ↓
Financial Sentiment Analysis
    ↓
Ticker Extraction + Entity Mapping
    ↓
Market Data Collection
    ↓
Technical Analysis Engine
    ↓
Signal Generation Engine
    ↓
LLM Reasoning Layer
    ↓
Risk Management Layer
    ↓
Trade Recommendation Engine
    ↓
Alert System + Dashboard
    ↓
Performance Tracking + Backtesting
```

---

# CORE REQUIREMENTS

## 1. News Monitoring Engine

The system must continuously monitor:

### Indian Financial News Sources

Primary targets:
- Moneycontrol
- Economic Times Markets
- LiveMint Markets
- Business Standard
- CNBC TV18
- NSE Announcements
- BSE Announcements
- RBI Press Releases
- SEBI Notifications
- Government Infrastructure Announcements
- PSU announcements
- Railway/Defense/Energy ministry updates

### News Categories To Track

The system should detect:

- Government contracts
- Earnings reports
- Mergers/acquisitions
- Buyback announcements
- Dividend announcements
- Promoter stake changes
- FII/DII activity
- Large orders/contracts
- Regulatory approvals
- Oil/gas discoveries
- Defense contracts
- RBI policy updates
- Budget announcements
- Sector-specific policies
- Manufacturing incentives
- Semiconductor incentives
- EV policy changes
- Telecom spectrum updates
- Banking regulation changes

---

# 2. News Processing Pipeline

The system should:

- Scrape or fetch latest articles
- Remove duplicates
- Remove spam
- Extract timestamps
- Extract source credibility
- Clean text
- Summarize long articles
- Detect important keywords

### Important Keywords

Examples:

Bullish:
- awarded
- contract
- profit rise
- expansion
- acquisition
- approval
- partnership
- production increase
- investment
- capacity expansion
- buyback

Bearish:
- investigation
- fraud
- decline
- loss
- debt
- downgrade
- bankruptcy
- weak guidance
- dilution
- regulatory action

---

# 3. Sentiment Analysis Engine

Use open-source financial sentiment models.

## Recommended Models

### Hugging Face Models

Priority models:
- ProsusAI/finbert
- yiyanghkust/finbert-tone
- distilbert-financial-news

The model should:

- Analyze headlines
- Analyze article summaries
- Produce:
  - sentiment score
  - confidence score
  - bullish/bearish classification

Example:

Input:
"ONGC receives ₹12,000 crore offshore drilling contract"

Output:
- Sentiment: Positive
- Confidence: 92%
- Market Impact: Bullish

---

# 4. Company/Ticker Mapping Engine

The system should map company mentions to NSE/BSE tickers.

Examples:

- Reliance Industries → RELIANCE
- ONGC → ONGC
- Tata Motors → TATAMOTORS
- BEL → Bharat Electronics Limited

The system should support:

- alias detection
- abbreviation detection
- fuzzy matching
- entity recognition

Recommended libraries:
- spaCy
- rapidfuzz
- transformers NER

---

# 5. Market Data Collection Engine

The system should fetch:

## Live/Recent Data

- OHLC candles
- Volume
- VWAP
- Delivery percentage
- Open interest
- Market depth
- Sector performance
- Index performance

## Historical Data

- Daily candles
- Hourly candles
- 15m candles
- Historical volume
- Historical volatility

## Recommended APIs/Libraries

Primary:
- yfinance
- NSEPython
- nsetools

Optional:
- Upstox API
- Zerodha Kite API

---

# 6. Technical Analysis Engine

The system must compute technical indicators.

## Required Indicators

### Trend Indicators
- EMA 20
- EMA 50
- EMA 200
- SMA

### Momentum Indicators
- RSI
- MACD
- Stochastic RSI

### Volatility Indicators
- ATR
- Bollinger Bands

### Volume Indicators
- Volume breakout
- OBV
- VWAP

### Price Action
- Support/resistance
- Breakout detection
- Consolidation detection
- Gap up/down detection
- Candlestick patterns

---

# 7. Signal Generation Engine

The system should combine:

- News sentiment
- Technical indicators
- Volume spikes
- Market context
- Sector momentum

And generate:

- BUY
- SELL
- HOLD
- WATCHLIST

Example:

BUY SIGNAL:
- Stock: BEL
- Reason:
  - Positive defense contract news
  - RSI breakout
  - MACD crossover
  - Volume spike
  - Defense sector momentum

Confidence:
- 84%

---

# 8. LLM Reasoning Layer

Use local LLMs for contextual analysis.

## Recommended Models

### Small Models
- Qwen 2.5
- Phi-3
- Gemma

### Medium Models
- Mistral
- Llama 3
- DeepSeek

## Recommended Runtime

- Ollama
- LM Studio
- llama.cpp

---

# LLM Responsibilities

The LLM should:

- Read summarized news
- Analyze technical indicators
- Analyze market conditions
- Analyze sentiment score
- Explain reasoning
- Rank opportunities
- Estimate short-term probability
- Suggest:
  - entry
  - stop loss
  - target
  - holding duration

---

# MASTER LLM PROMPT TEMPLATE

Use the following prompt template:

```text
You are an AI financial analysis assistant focused on Indian stock markets.

Your job is to evaluate whether a stock has bullish, bearish, or neutral short-term momentum.

You will receive:
- recent news
- sentiment score
- technical indicators
- volume information
- sector performance
- market trend

You must:
1. Analyze the information
2. Determine whether the stock is bullish or bearish
3. Suggest whether to BUY, SELL, HOLD, or WATCH
4. Suggest:
   - entry price
   - stop loss
   - target price
5. Estimate confidence percentage
6. Explain reasoning step-by-step
7. Consider risk management
8. Avoid overly aggressive recommendations
9. Avoid recommending trades with poor risk/reward ratio
10. Consider broader Indian market sentiment

Output format:

Recommendation: BUY
Confidence: 82%
Risk Level: Medium
Suggested Entry: ₹245
Suggested Stop Loss: ₹236
Suggested Target: ₹268
Suggested Holding Period: 3-10 trading days
Reasoning:
- Strong positive news sentiment
- MACD bullish crossover
- Volume breakout above 20-day average
- Defense sector showing momentum
- RSI indicates upward momentum but not overbought
```

---

# 9. Risk Management Engine

This is the MOST IMPORTANT component.

The system must strictly enforce:

## Capital Allocation

Rules:
- Never risk more than 2% to 5% of total capital on a single trade
- Never allocate more than 15% to one stock initially

For ₹30k capital:
- Max trade size: ₹3k–₹5k initially

---

# Stop Loss Enforcement

Every recommendation must include:

- stop loss
- risk/reward ratio

Minimum acceptable risk/reward:
- 1:2

Example:
- Risk: ₹3
- Target: ₹6+

---

# Daily/Weekly Drawdown Protection

System should stop generating aggressive trades if:

- Daily loss exceeds ₹1k
- Weekly loss exceeds ₹5k

System should enter:
- defensive mode
- low-risk mode

---

# 10. Portfolio Management Engine

The system should:

- Track active positions
- Track unrealized profit/loss
- Track portfolio allocation
- Avoid overexposure to one sector
- Recommend diversification

Example:

Avoid:
- 80% allocation into only banking stocks

Prefer:
- Banking
- Defense
- Pharma
- Energy
- IT

---

# 11. Backtesting Engine

The system MUST support backtesting.

## Recommended Libraries

- backtrader
- vectorbt
- zipline

Backtesting should evaluate:

- Win rate
- Average return
- Max drawdown
- Sharpe ratio
- Profit factor
- Strategy consistency

---

# 12. Alerting System

The system should send:

- Telegram alerts
- Discord alerts
- Web dashboard notifications

Example:

```text
BUY SIGNAL DETECTED

Stock: BEL
Entry: ₹312
Stop Loss: ₹303
Target: ₹338
Confidence: 81%
Reason:
Defense contract + breakout + bullish volume
```

---

# 13. Dashboard Requirements

Recommended:
- Streamlit
- Gradio
- React frontend

Dashboard should display:

## Watchlist
- Trending stocks
- AI-ranked opportunities

## Active Signals
- Buy/sell signals
- Confidence score

## Portfolio Tracking
- Current holdings
- Profit/loss

## Market Overview
- NIFTY trend
- BANKNIFTY trend
- Sector heatmap

## News Feed
- Important market news
- AI summaries

---

# 14. Data Storage

Use:
- SQLite initially
- PostgreSQL later

Store:
- News
- Signals
- Historical predictions
- Performance metrics
- Trade logs

---

# 15. Recommended Local Hardware

## Minimum
- 16GB RAM
- RTX 3060 or equivalent

## Recommended
- 32GB RAM
- RTX 4070/4080

## CPU-only Option
Use:
- quantized GGUF models
- llama.cpp

---

# 16. Recommended Software Stack

## Backend
- Python
- FastAPI

## AI/ML
- transformers
- torch
- sentence-transformers
- pandas
- numpy

## Technical Analysis
- ta
- pandas_ta

## Frontend
- Streamlit
- React

## LLM Runtime
- Ollama

## Queue/Workers
- Celery
- Redis

---

# 17. Suggested Folder Structure

```text
project/
│
├── data/
├── models/
├── news_engine/
├── sentiment_engine/
├── technical_engine/
├── llm_engine/
├── risk_engine/
├── portfolio_engine/
├── dashboard/
├── alerts/
├── backtesting/
├── logs/
├── config/
└── main.py
```

---

# 18. Advanced Future Features

Future upgrades:

- Reinforcement learning
- Multi-agent trading systems
- Sector rotation AI
- Options analysis
- Whale activity tracking
- Insider trading pattern detection
- Earnings prediction models
- Market regime detection
- AI-generated trading journal
- Auto portfolio balancing

---

# 19. Important Trading Principles

The AI should follow:

## Avoid FOMO
Do not chase stocks after huge spikes.

## Avoid Penny Stocks
Unless volume/liquidity criteria are satisfied.

## Prefer Liquidity
Trade liquid NSE stocks.

## Avoid Overtrading
Too many trades reduce performance.

## Prioritize Risk Management
Capital preservation is critical.

---

# 20. Suggested Initial Strategy

Recommended beginner strategy:

## News + Momentum Swing Trading

Conditions:
- Positive news detected
- Volume breakout
- RSI between 55 and 75
- MACD bullish crossover
- Sector showing strength

Holding period:
- 2 to 10 trading days

Avoid:
- Intraday scalping initially
- High leverage
- Options trading initially

---

# 21. Example Full Pipeline

Example:

1. News arrives:
"BEL receives major Indian defense contract"

2. Sentiment engine:
- Positive: 91%

3. Market engine:
- Volume spike detected
- MACD crossover detected
- RSI breakout detected

4. LLM analysis:
- Bullish short-term momentum likely

5. Risk engine:
- Trade size capped at ₹4k
- Stop loss calculated

6. Alert sent:

```text
BUY SIGNAL
Stock: BEL
Entry: ₹312
Target: ₹338
Stop Loss: ₹303
Confidence: 82%
```

---

# 22. Open Source Models To Use

## Financial Sentiment

- ProsusAI/finbert
- yiyanghkust/finbert-tone

## Embeddings

- bge-small-en
- all-MiniLM-L6-v2

## LLMs

- qwen2.5
- mistral
- llama3
- deepseek
- gemma

---

# 23. Recommended Development Roadmap

## Phase 1
Build:
- News scraper
- Sentiment analysis
- Telegram alerts

## Phase 2
Add:
- Technical indicators
- Signal generation

## Phase 3
Add:
- LLM reasoning
- Dashboard

## Phase 4
Add:
- Backtesting
- Portfolio management

## Phase 5
Add:
- Advanced AI
- Multi-agent systems
- Reinforcement learning

---

# 24. Important Legal/Safety Notes

The system:
- should NOT guarantee profits
- should NOT encourage reckless trading
- should NOT use excessive leverage
- should initially remain advisory only

Be aware of:
- SEBI regulations
- broker API restrictions
- rate limits

---

# 25. Final Goal

The final system should function as:

A local AI-powered Indian stock market research assistant capable of:

- reading market news
- analyzing technical indicators
- reasoning over market context
- generating trade ideas
- managing risk
- tracking performance
- continuously improving through historical evaluation

The system should prioritize:
- disciplined trading
- risk management
- explainable reasoning
- long-term profitability
- realistic expectations
- continuous learning

