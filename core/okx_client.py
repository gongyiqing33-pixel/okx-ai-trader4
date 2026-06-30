from __future__ import annotations

from typing import Any, Dict, Optional

from config.config import Settings
from core.utils.logger import setup_logger

try:
    from okx.v5 import Account# type: ignore
    from okx.v5 import Trade# type: ignore
except Exception:  # pragma: no cover - 在缺少 okx SDK 时使用模拟
    Account = None  # type: ignore
    Trade = None  # type: ignore


class OKXClient:
    """简单的 OKX SDK 包装，支持模拟与实盘模式。

    在没有安装 OKX SDK 时，会以模拟方式返回假数据，避免程序直接崩溃。
    """

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "okx_client")
        self._account = None
        self._trade = None
        if Account is not None and Trade is not None and self.settings.is_live():
            try:
                self._account = Account(api_key=self.settings.okx_api_key, api_secret=self.settings.okx_secret_key, passphrase=self.settings.okx_passphrase)
                self._trade = Trade(api_key=self.settings.okx_api_key, api_secret=self.settings.okx_secret_key, passphrase=self.settings.okx_passphrase)
                self.logger.info("OKX SDK 已初始化（实盘）")
            except Exception as exc:  # pragma: no cover - SDK 初始化异常
                self.logger.warning("初始化 OKX SDK 失败，回退到模拟模式: %s", exc)
                self._account = None
                self._trade = None

    def get_balance(self, currency: str = "USDT") -> float:
        """获取账户余额，实盘时使用 SDK，失败或模拟时返回默认值。"""
        if self.settings.is_simulation() or self._account is None:
            self.logger.info("使用模拟余额: %s", self.settings.initial_balance)
            return float(self.settings.initial_balance)
        try:
            resp = self._account.get_account_balance(currency=currency)  # type: ignore
            # 解析返回结果（SDK 返回格式可能不同，根据 SDK 文档调整）
            self.logger.info("余额查询返回: %s", resp)
            # 兜底解析
            return float(resp.get("data", [{}])[0].get("totalEq", self.settings.initial_balance))
        except Exception as exc:  # pragma: no cover - 网络或解析异常
            self.logger.warning("获取余额失败，使用模拟余额: %s", exc)
            return float(self.settings.initial_balance)

    def place_order(self, symbol: str, side: str, size: float, price: float, margin: float, stop_loss: float, take_profit: float, ord_type: str = "limit") -> Dict[str, Any]:
        """下单方法：实盘使用 SDK；默认使用模拟下单并记录信息。

        无论实盘或模拟，方法都会返回一个字典，包含 order 状态与细节，便于上层统一处理。
        """
        if self.settings.is_simulation() or self._trade is None:
            self.logger.info("模拟下单: %s %s %s@%s (%s)", side, symbol, size, price, ord_type)
            return {
                "status": "simulated",
                "symbol": symbol,
                "side": side,
                "size": size,
                "price": price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "ord_type": ord_type,
            }

        if not self.settings.auto_trade_enabled:
            raise PermissionError("实盘模式下必须启用 AUTO_TRADE_ENABLED 才能下单")

        try:
            # 真实下单（示例）：根据 SDK 文档构造请求
            self.logger.info("发送实盘下单请求: %s %s %s@%s (%s)", side, symbol, size, price, ord_type)
            ord_type_param = ord_type if ord_type in {"limit", "market"} else "limit"
            # 市价下单不需要 px
            if ord_type_param == "market":
                order_resp = self._trade.place_order(instId=symbol, tdMode="isolated", side=side, ordType="market", sz=str(size), tgtCcy="USDT")  # type: ignore
            else:
                order_resp = self._trade.place_order(instId=symbol, tdMode="isolated", side=side, ordType="limit", sz=str(size), px=str(price), tgtCcy="USDT")  # type: ignore
            self.logger.info("下单返回: %s", order_resp)
            return {"status": "sent", "resp": order_resp}
        except Exception as exc:  # pragma: no cover - 实盘下单异常
            self.logger.error("实盘下单失败: %s", exc)
            return {"status": "error", "error": str(exc)}
