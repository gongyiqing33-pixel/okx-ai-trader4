import os
import shutil
import unittest

from config.config import Settings
from core.okx_client import OKXClient


class OKXClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = "tests/tmp_okx"
        os.makedirs(self.tmp, exist_ok=True)
        self.settings = Settings.from_env()
        self.settings.log_dir = self.tmp
        self.settings.okx_flag = "1"
        self.settings.auto_trade_enabled = False

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.tmp)
        except Exception:
            pass

    def test_simulated_place_order_market(self) -> None:
        client = OKXClient(settings=self.settings)
        resp = client.place_order(symbol="BTC-USDT-SWAP", side="sell", size=0.001, price=60000.0, margin=6.0, stop_loss=59000.0, take_profit=62400.0, ord_type="market")
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp.get("status"), "simulated")
        self.assertEqual(resp.get("ord_type"), "market")


if __name__ == "__main__":
    unittest.main()
