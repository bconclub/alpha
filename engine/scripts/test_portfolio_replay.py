"""Deterministic research-engine checks; no network or exchange credentials."""
import unittest
from unittest.mock import patch
from portfolio_replay import Config, replay, signals, validate

START=36*7200


def fixture(pairs=('BTC',), prices=None):
    prices=prices or [(100,100,100,100)]
    candles={}
    for pair in pairs:
        rows=[dict(time=t,open=100,high=100,low=100,close=100)
              for t in range(0,START,300)]
        rows.extend(dict(time=START+i*300,open=o,high=h,low=l,close=c)
                    for i,(o,h,l,c) in enumerate(prices))
        candles[pair]=rows
    return dict(candles=candles,contracts={p:1 for p in pairs})


class ReplayTests(unittest.TestCase):
    def run_case(self,data,cfg=None,side=1,atr=2):
        end=data['candles']['BTC'][-1]['time']+300
        with patch('portfolio_replay.signals',return_value={START:(side,atr)}):
            return replay(data,cfg or Config(balance=30,margin=10,margin_cap=12),START,end)

    def test_minimum_contract_cannot_overspend(self):
        r=self.run_case(fixture(),Config(balance=6,margin_cap=12))
        self.assertEqual(r['closed_count'],0)
        self.assertEqual(r['skips']['size_or_margin'],1)
        self.assertFalse(r['open_positions'])

    def test_simultaneous_entries_reserve_margin(self):
        r=self.run_case(fixture(('BTC','ETH')),Config(balance=15,margin_cap=12))
        self.assertEqual(list(r['open_positions']),['BTC'])
        self.assertEqual(r['skips']['size_or_margin'],1)

    def test_stop_precedes_target_when_both_hit(self):
        r=self.run_case(fixture(prices=[(100,104,96,100)]))
        self.assertEqual(r['trades'][0]['reason'],'stop')
        self.assertLess(r['closed_net'],0)

    def test_take_profit_and_disable(self):
        data=fixture(prices=[(100,104,100,103)])
        r=self.run_case(data)
        self.assertEqual(r['trades'][0]['reason'],'profit_take')
        trail=self.run_case(data,Config(balance=30,margin=10,margin_cap=12,take_pct=0))
        self.assertEqual(trail['closed_count'],0)
        self.assertTrue(trail['open_positions'])

    def test_gap_does_not_fill_at_old_stop(self):
        r=self.run_case(fixture(prices=[(100,100,100,100),(90,91,89,90)]))
        self.assertEqual(r['trades'][0]['reason'],'gap_stop')
        self.assertLess(r['trades'][0]['exit'],90)

    def test_short_take_profit(self):
        r=self.run_case(fixture(prices=[(100,100,96,97)]),side=-1)
        self.assertEqual(r['trades'][0]['reason'],'profit_take')
        self.assertGreater(r['closed_net'],0)

    def test_open_profit_not_reported_realized(self):
        r=self.run_case(fixture(prices=[(100,101,100,101)]))
        self.assertEqual(r['closed_net'],0)
        self.assertGreater(r['end_equity'],r['end_cash'])

    def test_risk_budget_rejects_minimum(self):
        r=self.run_case(fixture(),Config(balance=6.77,margin_cap=12,risk_pct=1))
        self.assertFalse(r['open_positions'])

    def test_funding_charged_once_to_cash_and_trade(self):
        data=fixture(prices=[(100,100,100,100),(100,104,100,103)])
        data['funding']=[dict(time=START+300,pair='BTC',rate=.001,mark=100)]
        funded=self.run_case(data)
        del data['funding']
        baseline=self.run_case(data)
        self.assertAlmostEqual(baseline['end_cash']-funded['end_cash'],.1)
        self.assertAlmostEqual(baseline['closed_net']-funded['closed_net'],.1)

    def test_missing_candle_fails_closed(self):
        data=fixture();del data['candles']['BTC'][4]
        with self.assertRaises(ValueError):validate(data,Config())

    def test_signal_atr_includes_breakout_bar(self):
        data=fixture()
        r=data['candles']['BTC'][-2]
        r.update(high=114,close=114)
        event=signals(data['candles']['BTC'])[START]
        self.assertEqual(event[0],1)
        self.assertAlmostEqual(event[1],1)


if __name__=='__main__':unittest.main()
