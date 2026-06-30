from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config.config import Settings
from core.utils.logger import setup_logger


@dataclass
class OrderRequest:
    """订单请求对象。"""

    symbol: str
    side: str
    price: float
    size: float
    stop_loss: float
    take_profit: float
    margin: float
    ord_type: str = "limit"


@dataclass
class Position:
    """持仓对象。"""

    symbol: str
    side: str
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    margin: float
    realized_pnl: float = 0.0


class OrderManager:
    """订单管理器，当前以模拟下单为主，便于在 Codespaces 中测试。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "order")
        self.positions: list[Position] = []
        self.order_history: list[OrderRequest] = []

    def place_order(self, request: OrderRequest) -> dict:
        """下单。默认仅记录，不真正连接实盘。"""
        self.order_history.append(request)
        self.logger.info("模拟下单: %s %s 价格=%s 数量=%s", request.side, request.symbol, request.price, request.size)

        if self.settings.is_live() and not self.settings.auto_trade_enabled:
            raise PermissionError("实盘下单已被安全限制，必须显式开启 AUTO_TRADE_ENABLED。")

        if self.settings.is_simulation() or not self.settings.auto_trade_enabled:
            return {
                "status": "simulated",
                "symbol": request.symbol,
                "side": request.side,
                "price": request.price,
                "size": request.size,
                "stop_loss": request.stop_loss,
                "take_profit": request.take_profit,
            }

        return {
            "status": "sent",
            "symbol": request.symbol,
            "side": request.side,
            "price": request.price,
            "size": request.size,
            "stop_loss": request.stop_loss,
            "take_profit": request.take_profit,
        }
