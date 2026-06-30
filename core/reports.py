from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.config import Settings
from core.utils.logger import setup_logger


class DailyReport:
    """每日交易复盘与报告生成。"""

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "report")
        self.db_path = settings.database_path

    def _query_trades(self, days_back: int = 0) -> List[tuple]:
        """查询指定天数范围内的交易记录。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if days_back == 0:
                    # 今日交易
                    today = datetime.utcnow().date()
                    query = "SELECT * FROM trades WHERE DATE(ts) = ?"
                    cursor = conn.execute(query, (today.isoformat(),))
                else:
                    # 最近 N 天
                    start_date = (datetime.utcnow() - timedelta(days=days_back)).date()
                    query = "SELECT * FROM trades WHERE DATE(ts) >= ?"
                    cursor = conn.execute(query, (start_date.isoformat(),))
                return cursor.fetchall()
        except Exception as exc:  # pragma: no cover - 数据库异常
            self.logger.error("查询交易记录失败: %s", exc)
            return []

    def generate_daily_report(self) -> Dict[str, Any]:
        """生成当日交易报告。"""
        trades = self._query_trades(days_back=0)
        if not trades:
            report = {
                "date": datetime.utcnow().date().isoformat(),
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "daily_summary": "无交易记录",
            }
        else:
            total_trades = len(trades)
            total_pnl = sum(t[7] for t in trades)  # pnl 在第 8 列（index 7）
            winning_trades = sum(1 for t in trades if t[7] > 0)
            losing_trades = sum(1 for t in trades if t[7] < 0)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

            report = {
                "date": datetime.utcnow().date().isoformat(),
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "daily_summary": f"总交易数: {total_trades}, 胜率: {win_rate:.1f}%, 总盈亏: {total_pnl:.2f} USDT",
            }

        self.logger.info("每日报告: %s", report)
        self._save_report(report)
        return report

    def _save_report(self, report: Dict[str, Any]) -> None:
        """将报告保存到数据库。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS daily_reports (
                        id INTEGER PRIMARY KEY,
                        date TEXT NOT NULL UNIQUE,
                        total_trades INTEGER,
                        winning_trades INTEGER,
                        losing_trades INTEGER,
                        win_rate REAL,
                        total_pnl REAL,
                        summary TEXT
                    )
                """)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_reports 
                    (date, total_trades, winning_trades, losing_trades, win_rate, total_pnl, summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report["date"],
                        report["total_trades"],
                        report["winning_trades"],
                        report["losing_trades"],
                        report["win_rate"],
                        report["total_pnl"],
                        report["daily_summary"],
                    ),
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover - 数据库异常
            self.logger.error("保存报告失败: %s", exc)

    def get_monthly_summary(self) -> Dict[str, Any]:
        """获取本月汇总统计。"""
        trades = self._query_trades(days_back=30)
        if not trades:
            return {"total_trades": 0, "total_pnl": 0.0, "summary": "无交易记录"}

        total_trades = len(trades)
        total_pnl = sum(t[7] for t in trades)
        return {
            "total_trades": total_trades,
            "total_pnl": round(total_pnl, 2),
            "summary": f"30 天总交易数: {total_trades}, 总盈亏: {total_pnl:.2f} USDT",
        }
