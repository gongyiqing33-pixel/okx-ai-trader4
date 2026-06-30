from __future__ import annotations

from typing import Optional

from config.config import Settings
from core.market import MarketSnapshot
from core.strategy import SimpleStrategy
from core.utils.logger import setup_logger


class SignalGenerator:
    """将行情快照转成策略信号。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "signal")
        self.strategy = SimpleStrategy()

    def generate(self, snapshot: MarketSnapshot) -> tuple[bool, int, str, str]:
        """生成是否交易的结果。"""
        if len(snapshot.candles) < 3:
            raise ValueError("K 线数量不足，无法生成交易信号。")

        first_close = snapshot.candles[0].close_price
        last_close = snapshot.candles[-1].close_price
        price_change_pct = (last_close / first_close - 1.0) if first_close else 0.0

        volume_values = [candle.volume for candle in snapshot.candles]
        first_volume = volume_values[0]
        last_volume = volume_values[-1]
        volume_change_pct = (last_volume / first_volume - 1.0) if first_volume else 0.0

        recent_candles = [candle.close_price - candle.open_price for candle in snapshot.candles[-3:]]
        btc_change_pct = 0.0
        result = self.strategy.evaluate_signal(
            price_change_pct=price_change_pct,
            volume_change_pct=volume_change_pct,
            funding_rate=snapshot.funding_rate,
            recent_candles=recent_candles,
            btc_change_pct=btc_change_pct,
        )
        self.logger.info("策略评分: %s，等级: %s，原因: %s", result.score, result.level, result.reason)
        return result.should_trade, result.score, result.reason, result.level
