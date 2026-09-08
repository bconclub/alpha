"""Research only: chronological, capital-constrained OHLC replay. Never places orders.

Input JSON: {candles: {BTC: [{time,open,high,low,close}, ...]},
             contracts: {BTC: 0.001}, funding: [{time,pair,rate,mark}, ...]}.
Funding rate is positive when longs pay shorts. Contract units must match the
historical venue. Missing funding is explicitly reported, not treated as verified.
Five-minute OHLC cannot reproduce the live 12-second price path or API failures.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from alpha.strategy_v3 import _atr_rows


@dataclass(frozen=True)
class Config:
    balance: float = 14.14
    margin: float = 3.0
    margin_cap: float = 9.5
    leverage: float = 10.0
    max_open: int = 3
    fee: float = 0.00059  # scenario assumption, reconcile against actual fills
    slippage_bps: float = 5.0
    take_pct: float = 25.0  # zero disables target
    loss_pct: float = 26.0
    trail: float = 2.5
    daily_loss: float = 3.0
    kill_balance: float = 2.0
    risk_pct: float = 0.0  # zero reproduces fixed-margin sizing
    total_risk_pct: float = 0.0


def validate(data, cfg):
    for k, value in asdict(cfg).items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid {k}")
    if min(cfg.balance, cfg.margin, cfg.leverage, cfg.max_open, cfg.trail, cfg.loss_pct) <= 0:
        raise ValueError("Balance, sizing, leverage, slots, trail and loss cap must be positive")
    for pair, rows in data['candles'].items():
        if not rows or data['contracts'].get(pair, 0) <= 0:
            raise ValueError(f"Missing candles/contract units for {pair}")
        prev = None
        for r in rows:
            t = r['time']
            o, h, l, c = [float(r[k]) for k in ('open', 'high', 'low', 'close')]
            if t % 300 or (prev is not None and t != prev + 300):
                raise ValueError(f"Missing, duplicate or misaligned 5m data: {pair} {t}")
            if not all(math.isfinite(v) and v > 0 for v in (o,h,l,c)) or not l <= min(o,c) <= max(o,c) <= h:
                raise ValueError(f"Invalid OHLC: {pair} {t}")
            prev = t
    for f in data.get('funding', []):
        if (f['pair'] not in data['candles'] or f['time'] % 300
                or not math.isfinite(f['rate']) or not math.isfinite(f['mark']) or f['mark'] <= 0):
            raise ValueError('Invalid funding event')


def signals(rows):
    """Complete UTC 2h bars, prior-20 box, ATR includes just-closed signal bar."""
    buckets = {}
    for r in rows:
        buckets.setdefault(r['time'] // 7200, []).append(r)
    bars = []
    events = {}
    for bucket, rs in sorted(buckets.items()):
        if len(rs) != 24:
            continue
        bar = [bucket*7200, rs[0]['open'], max(r['high'] for r in rs),
               min(r['low'] for r in rs), rs[-1]['close'], 0]
        bars.append(bar)
        if len(bars) < 36:  # same minimum warmup as SignalEngine
            continue
        upper = max(b[2] for b in bars[-21:-1])
        lower = min(b[3] for b in bars[-21:-1])
        direction = 1 if bar[4] > upper else (-1 if bar[4] < lower else 0)
        events[(bucket+1)*7200] = (direction, _atr_rows(bars))
    return events


def replay(data, cfg, start, end, pairs=None):
    validate(data, cfg)
    pairs = list(pairs or data['candles'])  # deterministic priority, never hindsight ranked
    if start >= end or start % 300 or end % 300 or len(pairs) != len(set(pairs)) or not pairs:
        raise ValueError('Invalid interval or pair list')
    for pair in pairs:
        rows = data['candles'][pair]
        if rows[0]['time'] > start - 36*7200 or rows[-1]['time'] + 300 < end:
            raise ValueError(f'Insufficient warmup/evaluation coverage: {pair}')
    index = {p:{r['time']:r for r in data['candles'][p]} for p in pairs}
    sigs = {p:signals(data['candles'][p]) for p in pairs}
    times = sorted({t for p in pairs for t in index[p] if start <= t < end})
    funding = {}
    for event in data.get('funding', []):
        funding.setdefault(event['time'], []).append(event)
    cash = cfg.balance
    positions, closed, curve = {}, [], []
    skips = Counter()
    day, day_net = None, 0.0
    killed = False
    slip = cfg.slippage_bps / 10000

    def close(pair, price, ts, reason):
        nonlocal cash, day_net
        p = positions.pop(pair)
        fill = price * (1 - p['side']*slip)
        gross = p['side']*(fill-p['entry'])*p['units']
        fee = fill*p['units']*cfg.fee
        cash += gross-fee
        net = gross-fee-p['entry_fee']+p['funding']
        day_net += gross-fee  # fees/funding charged to day when incurred
        closed.append(dict(pair=pair, opened=p['opened'], closed=ts, reason=reason,
                           pnl=net, entry=p['entry'], exit=fill, margin=p['margin']))

    for t in times:
        if t//86400 != day:
            day, day_net = t//86400, 0.0
        for f in funding.get(t, []):
            if f['pair'] in positions:
                p = positions[f['pair']]
                amount = -p['side']*p['units']*f['mark']*f['rate']
                p['funding'] += amount
                cash += amount
                day_net += amount
        # Existing positions get gap exits before new allocations at this open.
        for pair in list(positions):
            p, r = positions[pair], index[pair][t]
            if t in sigs[pair]:
                p['atr'] = sigs[pair][t][1]
            cap = p['entry']*(1-p['side']*cfg.loss_pct/100/cfg.leverage)
            stop = max(p['stop'],cap) if p['side']==1 else min(p['stop'],cap)
            if p['side']*(r['open']-stop) <= 0:
                close(pair,r['open'],t,'gap_stop')
            elif t-p['opened'] >= 72*3600:
                close(pair,r['open'],t,'max_hold')
        if killed and cash >= cfg.kill_balance*1.5:
            killed = False
        if cash < cfg.kill_balance:
            killed = True
        for pair in pairs:
            signal = sigs[pair].get(t)
            if not signal or not signal[0] or pair in positions:
                continue
            if killed or day_net <= -cfg.daily_loss or len(positions)>=cfg.max_open:
                skips['portfolio_gate'] += 1
                continue
            side,a = signal
            price = index[pair][t]['open']*(1+side*slip)
            unit = data['contracts'][pair]
            per_contract_risk = (min(cfg.trail*a,price*cfg.loss_pct/100/cfg.leverage)
                                 +price*(2*cfg.fee+2*slip))*unit
            risk_equity = max(0, cash+sum(
                p['side']*(index[b][t]['open']-p['entry'])*p['units']
                -index[b][t]['open']*p['units']*cfg.fee for b,p in positions.items()))
            if cfg.risk_pct:
                n = math.floor(risk_equity*cfg.risk_pct/100/per_contract_risk)
            else:
                n = max(1,math.floor(cfg.margin*cfg.leverage/(price*unit)))
            margin = n*unit*price/cfg.leverage
            entry_fee = price*n*unit*cfg.fee
            free = cash-sum(p['margin'] for p in positions.values())
            # Also reserve adverse open MTM and estimated liquidation fee.
            free += sum(min(0,p['side']*(index[b][t]['open']-p['entry'])*p['units'])
                        for b,p in positions.items())
            reserve = sum(p['units']*index[b][t]['open']*cfg.fee for b,p in positions.items())
            risk = n*per_contract_risk
            if n<1 or margin>cfg.margin_cap or margin+2*entry_fee+reserve>free:
                skips['size_or_margin'] += 1
                continue
            if cfg.total_risk_pct and risk+sum(p['risk'] for p in positions.values())>risk_equity*cfg.total_risk_pct/100:
                skips['risk_budget'] += 1
                continue
            cash -= entry_fee
            day_net -= entry_fee
            positions[pair] = dict(side=side,entry=price,units=n*unit,margin=margin,
                                   stop=price-side*cfg.trail*a,atr=a,peak=price,
                                   opened=t,entry_fee=entry_fee,funding=0.0,risk=risk)
        # Unknown intrabar path: old protective level wins if stop and TP both hit.
        # New extrema only adjust the NEXT bar's trail, never retroactive exits.
        for pair in list(positions):
            p,r = positions[pair],index[pair][t]
            side = p['side']
            cap = p['entry']*(1-side*cfg.loss_pct/100/cfg.leverage)
            stop = max(p['stop'],cap) if side==1 else min(p['stop'],cap)
            hit = r['low']<=stop if side==1 else r['high']>=stop
            target = p['entry']*(1+side*cfg.take_pct/100/cfg.leverage)
            take = cfg.take_pct>0 and (r['high']>=target if side==1 else r['low']<=target)
            if hit:
                close(pair,stop,t+300,'stop')
            elif take:
                close(pair,target,t+300,'profit_take')
            else:
                p['peak'] = max(p['peak'],r['high']) if side==1 else min(p['peak'],r['low'])
                trail = p['peak']-side*cfg.trail*p['atr']
                p['stop'] = max(p['stop'],trail) if side==1 else min(p['stop'],trail)
        equity = cash+sum(p['side']*(index[b][t]['close']-p['entry'])*p['units']
                          -index[b][t]['close']*p['units']*cfg.fee for b,p in positions.items())
        curve.append(dict(time=t+300,equity=equity,cash=cash))
    peak,dd = cfg.balance,0.0
    for point in curve:
        peak=max(peak,point['equity']); dd=min(dd,point['equity']-peak)
    wins=sum(x['pnl'] for x in closed if x['pnl']>0)
    losses=-sum(x['pnl'] for x in closed if x['pnl']<0)
    return dict(config=asdict(cfg),start=start,end=end,pairs=pairs,
                closed_count=len(closed),closed_net=sum(x['pnl'] for x in closed),
                profit_factor=wins/losses if losses else None,
                end_cash=cash,end_equity=curve[-1]['equity'] if curve else cash,
                sampled_equity_max_drawdown=dd,skips=dict(skips),open_positions=positions,
                trades=closed,equity_curve=curve,
                funding_verified=bool(data.get('funding_verified',False)),
                limitations=['5m OHLC approximation, not live-fill parity',
                             'Drawdown sampled at bar close; intrabar loss may be larger',
                             'Contract metadata must be verified historically',
                             'No exchange liquidation, outage or restart simulation',
                             'Unverified funding must not support promotion'])


def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    return int(dt.replace(tzinfo=timezone.utc).timestamp() if dt.tzinfo is None else dt.timestamp())


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('data',type=Path)
    ap.add_argument('--start',required=True)
    ap.add_argument('--end',required=True)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--balance',type=float,default=14.14)
    ap.add_argument('--pairs',default='BTC,ETH,SOL,XRP,DOGE')
    ap.add_argument('--take-pct',type=float,default=25)
    ap.add_argument('--risk-pct',type=float,default=0)
    ap.add_argument('--total-risk-pct',type=float,default=0)
    args=ap.parse_args()
    result=replay(json.loads(args.data.read_text(encoding='utf-8-sig')),
                  Config(balance=args.balance,take_pct=args.take_pct,risk_pct=args.risk_pct,
                         total_risk_pct=args.total_risk_pct),timestamp(args.start),timestamp(args.end),
                  args.pairs.split(','))
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('trades','equity_curve','open_positions')},indent=2))


if __name__=='__main__':
    main()
