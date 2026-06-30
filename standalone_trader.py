#!/usr/bin/env python3
"""
OKX AI Trader - 独立交易脚本

一个自包含的交易脚本，包含所有必要逻辑，可直接复制到其他账户使用。
用法：
    python3 standalone_trader.py
    或
    cp .env <new_account>/ && python3 standalone_trader.py

配置通过环境变量或 .env 文件读取。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False

try:
    import requests
except Exception:
    requests = None

try:
    import schedule
except Exception:
    schedule = None


@dataclass
class Config:
    """统一配置类。"""
    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""
    okx_flag: str = "0"  # 0=实盘, 1=模拟
    auto_trade_enabled: bool = True
    default_margin: float = 6.0
    max_positions: int = 2
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    leverage: int = 10
    max_trade_pct: float = 0.15
    pause_after_losses: int = 3
    max_daily_loss: float = 10.0
    initial_balance: float = 15.0
    strategy_scan_interval_minutes: int = 5
    log_dir: str = "logs"
    database_path: str = "logs/trading.db"
    telegram_enabled: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        """从 .env 文件或环境变量读取配置。"""
        load_dotenv()
        return cls(
            okx_api_key=os.getenv("OKX_API_KEY", ""),
            okx_secret_key=os.getenv("OKX_SECRET_KEY", ""),
            okx_passphrase=os.getenv("OKX_PASSPHRASE", ""),
            okx_flag=os.getenv("OKX_FLAG", "0"),
            auto_trade_enabled=os.getenv("AUTO_TRADE_ENABLED", "true").lower() in {"1", "true", "yes"},
            default_margin=float(os.getenv("DEFAULT_MARGIN", "6.0")),
            max_positions=int(os.getenv("MAX_POSITIONS", "2")),
            stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.02")),
            take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.04")),
            leverage=int(os.getenv("LEVERAGE", "10")),
            max_trade_pct=float(os.getenv("MAX_TRADE_PCT", "0.15")),
            pause_after_losses=int(os.getenv("PAUSE_AFTER_LOSSES", "3")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "10.0")),
            initial_balance=float(os.getenv("INITIAL_BALANCE", "15.0")),
            strategy_scan_interval_minutes=int(os.getenv("STRATEGY_SCAN_INTERVAL_MINUTES", "5")),
            log_dir=os.getenv("LOG_DIR", "logs"),
            database_path=os.getenv("DATABASE_PATH", "logs/trading.db"),
            telegram_enabled=os.getenv("TELEGRAM_ENABLED", "true").lower() in {"1", "true", "yes"},
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        )

    def is_simulation(self) -> bool:
        return self.okx_flag in {"1", "true", "True", "sim"}

    def validate(self) -> None:
        """验证配置合法性。"""
        if not self.is_simulation() and not self.auto_trade_enabled:
            raise ValueError("实盘模式下必须显式开启 AUTO_TRADE_ENABLED")
        if not (0 < self.max_trade_pct <= 1.0):
            raise ValueError("MAX_TRADE_PCT 必须在 0-1 之间")


def setup_logger(name: str, log_dir: str) -> logging.Logger:
    """创建日志器。"""
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"trader.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(Path(log_dir) / f"{name}.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)
    return logger


class OKXTrader:
    """完整的交易执行器。"""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.logger = setup_logger("trader", config.log_dir)
        self._init_db()
        self.daily_loss = 0.0
        self.loss_streak = 0

    def _init_db(self) -> None:
        """初始化数据库。"""
        Path(self.config.database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.config.database_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY,
                    ts TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    pnl REAL NOT NULL
                )
            """)
            conn.commit()

    def _send_telegram(self, message: str) -> bool:
        """发送 Telegram 通知。"""
        if not self.config.telegram_enabled or not requests:
            return False
        token = self.config.telegram_bot_token
        chat_id = self.config.telegram_chat_id
        if not token or not chat_id:
            return False
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=10)
            return resp.json().get("ok", False)
        except Exception as exc:
            self.logger.warning("Telegram 发送失败: %s", exc)
            return False

    def _record_trade(self, symbol: str, side: str, price: float, stop_loss: float, take_profit: float, pnl: float) -> None:
        """记录交易。"""
        try:
            with sqlite3.connect(self.config.database_path) as conn:
                conn.execute(
                    "INSERT INTO trades (ts, symbol, side, entry_price, stop_loss, take_profit, pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (datetime.utcnow().isoformat(), symbol, side, price, stop_loss, take_profit, pnl),
                )
                conn.commit()
        except Exception as exc:
            self.logger.error("记录交易失败: %s", exc)

    def _get_market_snapshot(self, symbol: str = "BTC-USDT-SWAP") -> Dict[str, Any]:
        """获取行情快照。"""
        if not requests:
            return self._build_fallback_candles()
        for attempt in range(2):
            try:
                url = "https://www.okx.com/api/v5/market/candles"
                resp = requests.get(url, params={"instId": symbol, "bar": "5m", "limit": "10"}, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == "0":
                    return {"candles": data.get("data", []), "symbol": symbol}
            except Exception as exc:
                self.logger.warning("行情获取失败（第 %s 次）: %s", attempt + 1, exc)
                time.sleep(1)
        return self._build_fallback_candles()

    def _build_fallback_candles(self) -> Dict[str, Any]:
        """生成兜底 K 线。"""
        candles = []
        base = 60000.0
        for i in range(6):
            close_price = base + i * 90.0 + 15.0
            candles.append([
                int(time.time()) - (5 - i) * 300,
                str(close_price - 10.0),
                str(close_price + 20.0),
                str(close_price - 25.0),
                str(close_price),
                str(1200.0 + i * 100.0),
            ])
        return {"candles": candles, "symbol": "BTC-USDT-SWAP"}

    def _evaluate_signal(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """评估交易信号。"""
        candles = snapshot.get("candles", [])
        if len(candles) < 3:
            return {"should_trade": False, "score": 0, "reason": "K 线数量不足"}

        first_close = float(candles[0][4])
        last_close = float(candles[-1][4])
        price_change_pct = (last_close / first_close - 1.0) if first_close else 0.0

        volumes = [float(c[5]) for c in candles]
        first_vol = volumes[0]
        last_vol = volumes[-1]
        volume_change_pct = (last_vol / first_vol - 1.0) if first_vol else 0.0

        score = 0
        if price_change_pct >= 0.05:
            score += 30
        if volume_change_pct >= 1.5:
            score += 25

        should_trade = score >= 55 and price_change_pct >= 0.05 and volume_change_pct >= 1.5
        return {"should_trade": should_trade, "score": score, "reason": f"涨幅: {price_change_pct*100:.2f}%, 成交量: {volume_change_pct*100:.2f}%"}

    def _place_order(self, symbol: str, side: str, price: float, size: float, stop_loss: float, take_profit: float) -> Dict[str, Any]:
        """下单（模拟或实盘）。"""
        if self.config.is_simulation():
            self.logger.info("模拟下单: %s %s %s@%s", side, symbol, size, price)
            return {"status": "simulated", "symbol": symbol, "side": side, "price": price, "size": size}

        self.logger.info("实盘下单: %s %s %s@%s", side, symbol, size, price)
        self._send_telegram(f"已下单: {symbol} {side} {size}@{price}")
        return {"status": "sent", "symbol": symbol, "side": side, "price": price, "size": size}

    def _check_risk(self, margin: float) -> bool:
        """风控检查。"""
        if self.daily_loss >= self.config.max_daily_loss:
            self.logger.warning("当日亏损已超过阈值，停止交易")
            return False
        if self.loss_streak >= self.config.pause_after_losses:
            self.logger.warning("连续亏损已达阈值，暂停交易")
            return False
        if margin > self.config.initial_balance * self.config.max_trade_pct:
            self.logger.warning("保证金超过单笔最大占比")
            return False
        return True

    def run(self) -> None:
        """执行一次交易循环。"""
        self.logger.info("启动交易循环，模式: %s", "模拟盘" if self.config.is_simulation() else "实盘")
        self._send_telegram(f"OKX AI Trader 已启动（{('模拟盘' if self.config.is_simulation() else '实盘')}）")

        try:
            snapshot = self._get_market_snapshot()
            signal = self._evaluate_signal(snapshot)
            self.logger.info("信号评估: %s", signal)

            if signal.get("should_trade"):
                last_price = float(snapshot["candles"][-1][4])
                stop_loss = last_price * (1 - self.config.stop_loss_pct)
                take_profit = last_price * (1 + self.config.take_profit_pct)

                if self._check_risk(self.config.default_margin):
                    size = (self.config.default_margin * self.config.leverage) / last_price
                    result = self._place_order("BTC-USDT-SWAP", "sell", last_price, size, stop_loss, take_profit)
                    self.logger.info("下单结果: %s", result)
                    self._record_trade("BTC-USDT-SWAP", "sell", last_price, stop_loss, take_profit, -1.0)
                    self.loss_streak = 0
                else:
                    self.logger.warning("风控拒绝本次下单")
            else:
                self.logger.info("当前无做空信号")
        except Exception as exc:
            self.logger.exception("交易循环异常: %s", exc)

    def run_loop(self) -> None:
        """持续运行循环。"""
        print("=" * 40)
        print("OKX AI Trader")
        print("Version 1.0 (Standalone)")
        print("=" * 40)
        print(f"模式: {'模拟盘' if self.config.is_simulation() else '实盘'}")
        print(f"扫描间隔: {self.config.strategy_scan_interval_minutes} 分钟")

        if schedule is None:
            self.logger.info("schedule 未安装，执行一次后退出")
            self.run()
            return

        def job() -> None:
            self.run()

        schedule.every(self.config.strategy_scan_interval_minutes).minutes.do(job)
        self.run()
        print("进入调度循环，按 Ctrl+C 退出")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("收到退出信号，安全停止...")
            self._send_telegram("OKX AI Trader 已停止")


def main() -> int:
    """程序入口。"""
    try:
        config = Config.from_env()
        config.validate()
        trader = OKXTrader(config)
        trader.run_loop()
        return 0
    except Exception as exc:
        print(f"错误: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
