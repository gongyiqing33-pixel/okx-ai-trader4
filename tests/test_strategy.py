import unittest

from core.strategy import SignalScore, SignalResult, SimpleStrategy


class StrategyTestCase(unittest.TestCase):
    def test_score_and_signal(self) -> None:
        strategy = SimpleStrategy()
        result = strategy.evaluate_signal(
            price_change_pct=0.07,
            volume_change_pct=2.0,
            funding_rate=-0.0001,
            recent_candles=[0.03, 0.01, -0.01],
            btc_change_pct=-0.01,
        )
        self.assertIsInstance(result, SignalResult)
        self.assertGreaterEqual(result.score, 0)
        self.assertLessEqual(result.score, 100)
        self.assertTrue(result.should_trade)

    def test_score_for_weak_signal(self) -> None:
        strategy = SimpleStrategy()
        result = strategy.evaluate_signal(
            price_change_pct=0.01,
            volume_change_pct=1.0,
            funding_rate=0.0002,
            recent_candles=[0.01, 0.005, 0.003],
            btc_change_pct=0.01,
        )
        self.assertFalse(result.should_trade)


if __name__ == "__main__":
    unittest.main()
