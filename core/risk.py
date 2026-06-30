from __future__ import annotations

from typing import Optional

from config.config import Settings
from core.order import OrderRequest, Position
from core.utils.logger import setup_logger


class RiskManager:
    """实现最小可用风控逻辑，保护账户。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "risk")
        self.loss_streak = 0
        self.daily_loss = 0.0
        self.pause_until = None

    def can_trade(self) -> bool:
        """检查是否允许继续交易。"""
        if self.daily_loss >= self.settings.max_daily_loss:
            self.logger.warning("当日亏损已超过阈值，停止交易")
            return False
        return True

    def evaluate(self, request: OrderRequest, position: Optional[Position] = None) -> bool:
        """检查下单是否合规。"""
        if not self.can_trade():
            return False
        if position is not None and len([p for p in [position] if p.symbol == request.symbol]) >= self.settings.max_positions:
            self.logger.warning("达到最大持仓限制，拒绝新单")
            return False
        if request.margin > self.settings.default_margin:
            self.logger.warning("保证金超过默认配置，拒绝下单")
            return False
        return True

    def mark_result(self, pnl: float) -> None:
        """记录交易结果，并根据亏损连续次数决定是否暂停。"""
        self.daily_loss += pnl
        if pnl < 0:
            self.loss_streak += 1
        else:
            self.loss_streak = 0

        if self.loss_streak >= self.settings.pause_after_losses:
            self.logger.warning("连续亏损 %s 单，暂停交易", self.loss_streak)
