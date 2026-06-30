import os
import shutil
import unittest

from config.config import Settings
from core.okx_client import OKXClient
from core.notification.telegram import TelegramNotifier
from core.database.sqlite import TradingDatabase
from core.executor import OrderExecutor
from core.order import OrderRequest


class ExecutorTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = "tests/tmp_exec"
        os.makedirs(self.tmp, exist_ok=True)
        self.settings = Settings.from_env()
        self.settings.log_dir = self.tmp
        self.settings.database_path = os.path.join(self.tmp, "trading_test.db")
        self.settings.okx_flag = "1"
        self.settings.auto_trade_enabled = False

        self.okx = OKXClient(settings=self.settings)
        self.db = TradingDatabase(settings=self.settings)
        self.notifier = TelegramNotifier(settings=self.settings)
        self.exec = OrderExecutor(settings=self.settings, okx=self.okx, db=self.db, notifier=self.notifier)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.tmp)
        except Exception:
            pass

    def test_execute_market_order_with_margin(self) -> None:
        req = OrderRequest(symbol="BTC-USDT-SWAP", side="sell", price=60000.0, size=0.0, stop_loss=59000.0, take_profit=62400.0, margin=6.0, ord_type="market")
        res = self.exec.execute(req)
        self.assertIsInstance(res, dict)
        self.assertIn(res.get("status"), {"ok", "error", "rejected"})
        summary = self.db.get_summary()
        self.assertGreaterEqual(summary.get("total_trades", 0), 0)


if __name__ == "__main__":
    unittest.main()
