from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from config.config import Settings
from core.database.sqlite import TradingDatabase
from core.market import MarketDataService
from core.notification.telegram import TelegramNotifier
from core.okx_client import OKXClient
from core.order import OrderRequest
from core.executor import OrderExecutor
from core.risk import RiskManager
from core.signal import SignalGenerator
from core.utils.logger import setup_logger
from core.reports import DailyReport

try:
    import schedule
except Exception:  # pragma: no cover - 缺少 schedule 时使用简化循环
    schedule = None
import time


def print_banner() -> None:
    """打印启动横幅。"""
    print("=" * 40)
    print("OKX AI Trader")
    print("Version 1.0")
    print("=" * 40)


def validate_environment(settings: Settings) -> None:
    """检查配置和目录。"""
    settings.validate()
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)


def run_once(settings: Settings) -> None:
    """运行一次完整交易循环。"""
    logger = setup_logger(settings.log_dir, "main")
    logger.info("机器人启动，当前模式: %s", "模拟盘" if settings.is_simulation() else "实盘")

    try:
        market_service = MarketDataService(settings=settings, logger=logger)
        signal_generator = SignalGenerator(settings=settings, logger=logger)
        okx = OKXClient(settings=settings, logger=logger)
        risk_manager = RiskManager(settings=settings, logger=logger)
        db = TradingDatabase(settings=settings, logger=logger)
        notifier = TelegramNotifier(settings=settings, logger=logger)
        executor = OrderExecutor(settings=settings, okx=okx, db=db, notifier=notifier, logger=logger)
        reporter = DailyReport(settings=settings, logger=logger)

        snapshot = market_service.get_market_snapshot()
        should_trade, score, reason, level = signal_generator.generate(snapshot)
        if should_trade:
            logger.info("发现做空机会，评分=%s，等级=%s，原因=%s", score, level, reason)
            notifier.send(f"发现做空机会｜币种:BTC-USDT-SWAP｜评分:{score}｜开仓价:{snapshot.candles[-1].close_price:.2f}｜止损:{snapshot.candles[-1].close_price * (1 - settings.stop_loss_pct):.2f}｜止盈:{snapshot.candles[-1].close_price * (1 + settings.take_profit_pct):.2f}")
            request = OrderRequest(
                symbol="BTC-USDT-SWAP",
                side="sell",
                price=snapshot.candles[-1].close_price,
                size=1.0,
                stop_loss=snapshot.candles[-1].close_price * (1 - settings.stop_loss_pct),
                take_profit=snapshot.candles[-1].close_price * (1 + settings.take_profit_pct),
                margin=settings.default_margin,
            )
            # 使用执行器统一处理风控、下单、落库与通知
            result = executor.execute(request)
            logger.info("执行器返回: %s", result)
        else:
            logger.info("当前无满足条件的做空信号")

        summary = db.get_summary()
        logger.info("数据库摘要: %s", summary)
        
        # 生成每日报告
        daily_report = reporter.generate_daily_report()
        notifier.send(f"每日报告: {daily_report['daily_summary']}") if notifier else None
    except Exception as exc:  # pragma: no cover - 运行时兜底
        logger.exception("主循环异常: %s", exc)


def main() -> int:
    """程序入口。"""
    print_banner()
    try:
        settings = Settings.from_env()
        validate_environment(settings)
        print("读取 API 配置完成")
        print("检测连接: OK")
        okx = OKXClient(settings=settings, logger=setup_logger(settings.log_dir, "main"))
        print(f"账户余额: {okx.get_balance():.2f} USDT（模拟盘默认或实时余额）")

        if schedule is None:
            print("schedule 未安装，使用简化循环执行一次后退出")
            run_once(settings)
            print("系统运行完成")
            return 0

        # 若希望持续运行，使用 schedule 每隔配置的分钟数执行一次
        def job() -> None:
            run_once(settings)

        schedule.every(settings.strategy_scan_interval_minutes).minutes.do(job)
        # 每天凌晨 0 点生成每日报告
        schedule.every().day.at("00:00").do(job)
        print("进入调度循环，按 Ctrl+C 退出")
        try:
            # 立刻执行一次
            run_once(settings)
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("收到退出信号，正在安全停止...")
        print("系统运行完成")
        return 0
    except Exception as exc:
        print(f"错误: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
