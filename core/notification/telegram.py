from __future__ import annotations

import time
from typing import Optional

from config.config import Settings
from core.utils.logger import setup_logger

try:
    import requests
except Exception:  # pragma: no cover - 运行环境缺少 requests 时使用兜底
    requests = None


class TelegramNotifier:
    """Telegram 通知封装。

    若 `Settings.telegram_enabled` 为 True 且配置了 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`，
    则尝试通过 Telegram Bot API 发送消息；否则记录日志并返回 False。
    """

    def __init__(self, settings: Settings, logger: Optional[object] = None) -> None:
        self.settings = settings
        self.logger = logger or setup_logger(settings.log_dir, "telegram")

    def send(self, message: str) -> bool:
        """发送通知，返回是否成功。

        包含简单重试机制和错误日志记录，保证在网络或配置异常时不会抛出未捕获异常。
        """
        if not self.settings.telegram_enabled:
            self.logger.info("Telegram 未启用，跳过通知: %s", message)
            return False

        token = self.settings.telegram_bot_token
        chat_id = self.settings.telegram_chat_id
        if not token or not chat_id:
            self.logger.error("Telegram 配置不完整，TOKEN 或 CHAT_ID 缺失")
            return False

        if requests is None:
            self.logger.error("缺少 requests 库，无法发送 Telegram 消息")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}

        for attempt in range(3):
            try:
                resp = requests.post(url, data=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    self.logger.info("Telegram 发送成功: %s", message)
                    return True
                else:
                    self.logger.warning("Telegram 返回非 ok: %s", data)
            except Exception as exc:  # pragma: no cover - 运行时网络或 API 错误
                self.logger.warning("Telegram 发送失败（第 %s 次）: %s", attempt + 1, exc)
                time.sleep(1 * (attempt + 1))

        self.logger.error("Telegram 发送最终失败: %s", message)
        return False
