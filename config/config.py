from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - 运行环境缺少 python-dotenv 时使用兜底
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False


@dataclass
class Settings:
    """统一管理运行时配置。"""

    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""
    okx_flag: str = "1"
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
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    auto_trade_enabled: bool = False

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "Settings":
        """从环境变量或 .env 文件读取配置。"""
        env_file = Path(env_path or ".env")
        if env_file.exists():
            load_dotenv(env_file, override=False)
        else:
            load_dotenv(override=False)

        return cls(
            okx_api_key=os.getenv("OKX_API_KEY", ""),
            okx_secret_key=os.getenv("OKX_SECRET_KEY", ""),
            okx_passphrase=os.getenv("OKX_PASSPHRASE", ""),
            okx_flag=os.getenv("OKX_FLAG", "1"),
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
            telegram_enabled=os.getenv("TELEGRAM_ENABLED", "false").lower() in {"1", "true", "yes"},
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            auto_trade_enabled=os.getenv("AUTO_TRADE_ENABLED", "false").lower() in {"1", "true", "yes"},
        )

    def is_simulation(self) -> bool:
        """判断是否处于模拟盘模式。"""
        return self.okx_flag in {"1", "true", "True", "sim", "SIM", "simulation"}

    def is_live(self) -> bool:
        """判断是否启用实盘。"""
        return not self.is_simulation()

    def validate(self) -> None:
        """验证参数合法性，并阻止默认实盘连接。"""
        if self.is_live() and not self.auto_trade_enabled:
            raise ValueError("实盘模式下必须显式开启 AUTO_TRADE_ENABLED，默认不允许自动下单。")
        if self.is_live() and not all([self.okx_api_key, self.okx_secret_key, self.okx_passphrase]):
            raise ValueError("实盘模式需要配置 OKX_API_KEY、OKX_SECRET_KEY 和 OKX_PASSPHRASE。")
        if self.leverage <= 0:
            raise ValueError("杠杆倍数必须大于 0。")
        if self.max_positions <= 0:
            raise ValueError("最大持仓数量必须大于 0。")
        if not (0 < self.max_trade_pct <= 1.0):
            raise ValueError("MAX_TRADE_PCT 必须在 0-1 之间，例如 0.15 表示 15% 的账户资金。")
