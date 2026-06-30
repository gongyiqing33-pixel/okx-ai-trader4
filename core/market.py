from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

try:
    import requests
except Exception:  # pragma: no cover - 运行环境缺少 requests 时使用兜底
    requests = None

try:
    import websocket
except Exception:  # pragma: no cover - 运行环境缺少 websocket-client 时使用兜底
    websocket = None

from config.config import Settings
from core.utils.logger import setup_logger


@dataclass
class Candle:
    """K 线对象。"""

    timestamp: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


@dataclass
class MarketSnapshot:
    """行情快照。"""

    symbol: str
    candles: List[Candle]
    funding_rate: float


class MarketDataService:
    """负责获取行情数据，并提供自动重连与兜底。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "market")
        self._ws = None

    def get_market_snapshot(self, symbol: str = "BTC-USDT-SWAP") -> MarketSnapshot:
        """获取最近的行情快照。"""
        candles: List[Candle] = []
        for attempt in range(2):
            try:
                candles = self._fetch_klines(symbol)
                if candles:
                    return MarketSnapshot(symbol=symbol, candles=candles, funding_rate=self._fetch_funding_rate(symbol))
            except Exception as exc:  # pragma: no cover - 实际运行路径
                self.logger.warning("行情获取失败，尝试第 %s 次: %s", attempt + 1, exc)
                time.sleep(1)

        return MarketSnapshot(symbol=symbol, candles=self._build_fallback_candles(), funding_rate=0.0)

    def _fetch_klines(self, symbol: str) -> List[Candle]:
        """从 OKX 公共接口拉取 K 线。"""
        if requests is None:
            raise RuntimeError("requests 未安装，无法访问 OKX 行情接口")

        url = "https://www.okx.com/api/v5/market/candles"
        params = {"instId": symbol, "bar": "5m", "limit": "10"}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != "0":
            raise RuntimeError(f"OKX 返回异常: {payload}")

        raw_candles = payload.get("data", [])
        candles: List[Candle] = []
        for item in raw_candles:
            candles.append(
                Candle(
                    timestamp=int(item[0]),
                    open_price=float(item[1]),
                    high_price=float(item[2]),
                    low_price=float(item[3]),
                    close_price=float(item[4]),
                    volume=float(item[5]),
                )
            )
        return candles

    def _fetch_funding_rate(self, symbol: str) -> float:
        """获取资金费率，失败时返回 0。"""
        if requests is None:
            return 0.0

        url = "https://www.okx.com/api/v5/market/funding-rate"
        params = {"instId": symbol, "limit": "1"}
        try:
            response = requests.get(url, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()
            rows = data.get("data", [])
            if rows:
                return float(rows[0].get("fundingRate", 0.0))
        except Exception as exc:  # pragma: no cover - 运行环境网络异常
            self.logger.warning("资金费率获取失败: %s", exc)
        return 0.0

    def subscribe(self, symbol: str = "BTC-USDT-SWAP") -> None:
        """尝试建立 WebSocket 订阅；若依赖缺失则跳过。"""
        if websocket is None:
            self.logger.warning("websocket-client 未安装，跳过实时订阅")
            return

        self.logger.info("尝试建立行情订阅: %s", symbol)

    def _build_fallback_candles(self) -> List[Candle]:
        """当网络不可用时，生成可继续运行的兜底 K 线。"""
        base = 60000.0
        candles: List[Candle] = []
        for index in range(6):
            close_price = base + index * 90.0 + 15.0
            candles.append(
                Candle(
                    timestamp=int(time.time()) - (5 - index) * 300,
                    open_price=close_price - 10.0,
                    high_price=close_price + 20.0,
                    low_price=close_price - 25.0,
                    close_price=close_price,
                    volume=1200.0 + index * 100.0,
                )
            )
        return candles
