"""Download public Delta India candles and current contract metadata; no auth."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from portfolio_replay import timestamp

BASE='https://api.india.delta.exchange/v2'


def get(path):
    for attempt in range(3):
        try:
            req=urllib.request.Request(BASE+path,headers={'User-Agent':'Alpha-research-audit'})
            payload=json.load(urllib.request.urlopen(req,timeout=30))
            if not payload.get('success',False):raise ValueError('Exchange unsuccessful response')
            return payload['result']
        except Exception:
            if attempt==2:raise
            time.sleep(2**attempt)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--start',required=True)
    ap.add_argument('--end',required=True)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    start,end=timestamp(args.start),timestamp(args.end)
    if start>=end or end>int(time.time())//300*300:raise ValueError('Invalid completed-bar interval')
    products=get('/products')
    contracts={}
    for p in products:
        for pair in ('BTC','ETH','SOL','XRP','DOGE'):
            if p['symbol']==pair+'USD':contracts[pair]=float(p['contract_value'])
    if len(contracts)!=5:raise ValueError('Missing perpetual metadata')
    candles={}
    for pair in contracts:
        rows={}
        cur=(start-5*86400)//300*300
        while cur<end:
            stop=min(cur+1500*300,end)
            for r in get(f'/history/candles?resolution=5m&symbol={pair}USD&start={cur}&end={stop}'):
                if cur<=r['time']<end:rows[r['time']]=r
            cur=stop
        candles[pair]=sorted(rows.values(),key=lambda r:r['time'])
        print(pair,len(candles[pair]),flush=True)
    payload=dict(candles=candles,contracts=contracts,funding_verified=False,
                 source=BASE,retrieved_at=datetime.now(timezone.utc).isoformat(),
                 metadata_warning='Current contract values; historical validity unverified')
    raw=json.dumps(payload,sort_keys=True).encode()
    args.output.write_bytes(raw)
    print('SHA256',hashlib.sha256(raw).hexdigest())


if __name__=='__main__':main()
