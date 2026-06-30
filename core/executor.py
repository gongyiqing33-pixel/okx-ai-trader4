from __future__ import annotations

from typing import Optional

from config.config import Settings
from core.okx_client import OKXClient
from core.order import OrderRequest, Position
from core.database.sqlite import TradingDatabase
from core.notification.telegram import TelegramNotifier
from core.risk import RiskManager
from core.utils.logger import setup_logger


class OrderExecutor:
    """安全下单执行器：集中风控检查、下单执行、落库与通知。

    目标是把下单逻辑从主流程中抽离，确保所有异常在此捕获并记录。
    """

    def __init__(self, settings: Settings, okx: OKXClient, db: TradingDatabase, notifier: TelegramNotifier, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.okx = okx
        self.db = db
        self.notifier = notifier
        self.logger = logger or setup_logger(settings.log_dir, "executor")
        self.risk = RiskManager(settings=settings, logger=self.logger)

    def execute(self, request: OrderRequest) -> dict:
        """执行下单：包括风控、调用 OKX 客户端、记录与通知。

        返回包含最终状态的字典。
        """
        try:
            # 根据当前账户余额与最大单笔占比限制保证金
            try:
                account_balance = float(self.okx.get_balance())
            except Exception:
                account_balance = float(self.settings.initial_balance)

            allowed_margin = account_balance * float(self.settings.max_trade_pct)
            if request.margin > allowed_margin:
                self.logger.warning("请求保证金 %s 超过允许的单笔最大占比 %s，已调整为 %s", request.margin, self.settings.max_trade_pct, allowed_margin)
                request.margin = allowed_margin

            # 若未指定数量，则按保证金与杠杆估算下单数量（简化计算）
            if request.size <= 0.0 and request.price > 0:
                try:
                    request.size = (request.margin * self.settings.leverage) / float(request.price)
                except Exception:
                    request.size = 0.0

            # 风控检查
            if not self.risk.evaluate(request):
                self.logger.warning("风控阻止下单: %s", request)
                return {"status": "rejected", "reason": "risk"}

            # 执行下单
            resp = self.okx.place_order(
                symbol=request.symbol,
                side=request.side,
                size=request.size,
                price=request.price,
                margin=request.margin,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                ord_type=getattr(request, "ord_type", "limit"),
            )

            # 记录（模拟或实盘）
            pnl = 0.0
            try:
                self.db.record_trade(request.symbol, request.side, request.price, request.stop_loss, request.take_profit, pnl)
            except Exception as exc:  # pragma: no cover - 数据库异常
                self.logger.error("记录交易异常: %s", exc)

            # 通知
            try:
                self.notifier.send(f"已下单: {request.symbol} {request.side} {request.size}@{request.price}（{resp.get('status')}）")
            except Exception as exc:  # pragma: no cover - 通知异常
                self.logger.error("发送通知异常: %s", exc)

            return {"status": "ok", "resp": resp}
        except Exception as exc:  # pragma: no cover - 兜底异常
            self.logger.exception("下单执行异常: %s", exc)
            return {"status": "error", "error": str(exc)}
