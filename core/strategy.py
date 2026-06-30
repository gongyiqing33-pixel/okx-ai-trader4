from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SignalScore:
    """策略评分结果。"""

    score: int
    level: str


@dataclass
class SignalResult:
    """最终交易信号。"""

    should_trade: bool
    score: int
    reason: str
    level: str


class SimpleStrategy:
    """一个简洁但可运行的空头策略，基于 5 分钟 K 线指标。"""

    def __init__(self) -> None:
        self.min_score: int = 90

    def evaluate_signal(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        funding_rate: Optional[float],
        recent_candles: List[float],
        btc_change_pct: float,
    ) -> SignalResult:
        """根据多项指标生成做空信号。"""
        score: int = 0
        reason_parts: List[str] = []

        if price_change_pct >= 0.05:
            score += 30
            reason_parts.append("最近 5 分钟上涨超过 5%")
        if volume_change_pct >= 1.5:
            score += 25
            reason_parts.append("成交量增加超过 150%")
        if recent_candles and len(recent_candles) >= 3:
            if recent_candles[-1] > 0 and recent_candles[-2] > 0 and recent_candles[-3] > 0:
                score += 10
                reason_parts.append("最近三根 K 线呈现弱势滞涨")
        if funding_rate is not None and funding_rate < 0:
            score += 5
            reason_parts.append("资金费率偏低")
        if btc_change_pct >= 0.03:
            score -= 25
            reason_parts.append("BTC 最近 30 分钟暴涨，过滤信号")

        score = max(0, min(100, score))
        if score >= 90 and price_change_pct >= 0.05 and volume_change_pct >= 1.5:
            should_trade = True
        else:
            should_trade = False

        if score >= 90:
            level = "强烈"
        elif score >= 80:
            level = "轻仓"
        else:
            level = "放弃"

        return SignalResult(
            should_trade=should_trade,
            score=score,
            reason="; ".join(reason_parts) if reason_parts else "无明显做空特征",
            level=level,
        )
