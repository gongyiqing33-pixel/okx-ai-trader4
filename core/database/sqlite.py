from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.config import Settings
from core.utils.logger import setup_logger


class TradingDatabase:
    """轻量 SQLite 数据库，保存交易和绩效信息。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "db")
        self.db_path = Path(settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    pnl REAL NOT NULL
                )
                """
            )
            conn.commit()

    def record_trade(self, symbol: str, side: str, entry_price: float, stop_loss: float, take_profit: float, pnl: float) -> None:
        """插入交易记录。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO trades (ts, symbol, side, entry_price, stop_loss, take_profit, pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (datetime.utcnow().isoformat(), symbol, side, entry_price, stop_loss, take_profit, pnl),
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover - 数据库异常
            self.logger.error("记录交易失败: %s", exc)

    def get_summary(self) -> dict:
        """读取绩效摘要。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(pnl), 0) FROM trades")
                count, total_pnl = cursor.fetchone()
                return {"total_trades": count or 0, "total_pnl": float(total_pnl or 0.0)}
        except Exception as exc:  # pragma: no cover - 数据库异常
            self.logger.error("读取绩效摘要失败: %s", exc)
            return {"total_trades": 0, "total_pnl": 0.0}
