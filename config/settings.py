"""Application settings loaded from environment and defaults."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    project_root: Path = PROJECT_ROOT
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'stock_predictor.db'}"
    models_cache_dir: Path = PROJECT_ROOT / "models" / "cache"
    logs_dir: Path = PROJECT_ROOT / "logs"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: float = 120.0

    # Hardware
    use_cpu_only: bool = False
    finbert_batch_size: int = 8

    # Capital & risk (INR)
    total_capital: float = 30_000.0
    max_risk_pct_per_trade: float = 0.05
    min_risk_pct_per_trade: float = 0.02
    max_allocation_pct_per_stock: float = 0.15
    max_trade_size_inr: float = 5_000.0
    min_trade_size_inr: float = 3_000.0
    max_daily_loss: float = 1_000.0
    max_weekly_loss: float = 5_000.0
    min_risk_reward_ratio: float = 2.0

    # Trading principles
    min_stock_price_inr: float = 50.0
    min_avg_volume: int = 100_000
    max_day_spike_pct: float = 8.0
    max_sector_concentration_pct: float = 0.30

    # Swing strategy (Step 20)
    rsi_buy_min: float = 55.0
    rsi_buy_max: float = 75.0
    volume_breakout_multiplier: float = 1.5

    # Pipeline
    scrape_interval_minutes: int = 30
    top_signals_for_llm: int = 5
    request_delay_seconds: float = 1.5
    user_agent: str = (
        "Mozilla/5.0 (compatible; StockPredictor/1.0; +local-research-bot)"
    )

    # Default watchlist
    default_watchlist: list[str] = [
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "ICICIBANK",
        "SBIN",
        "BHARTIARTL",
        "ITC",
        "BEL",
        "ONGC",
        "TATAMOTORS",
        "ADANIENT",
    ]

    # Sentiment model
    finbert_model_id: str = "ProsusAI/finbert"

    @property
    def max_risk_per_trade_inr(self) -> float:
        return self.total_capital * self.max_risk_pct_per_trade

    @property
    def max_allocation_inr(self) -> float:
        return self.total_capital * self.max_allocation_pct_per_stock


@lru_cache
def get_settings() -> Settings:
    return Settings()
