"""Fixed research comparisons; no optimization, no promotion, no live orders."""
import argparse
import hashlib
import json
from pathlib import Path
from portfolio_replay import Config,replay,timestamp


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('data',type=Path)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--balance',type=float,default=14.14)
    ap.add_argument('--start',default='2026-06-15')
    ap.add_argument('--split',default='2026-08-23')
    ap.add_argument('--end',default='2026-09-08')
    args=ap.parse_args()
    if not timestamp(args.start)<timestamp(args.split)<timestamp(args.end):
        raise ValueError('Require start < split < end')
    raw=args.data.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
    pairs=['BTC','ETH','SOL','XRP','DOGE']
    scenarios=[('current',Config(balance=args.balance),pairs),
               ('trail_only',Config(balance=args.balance,take_pct=0),pairs),
               ('without_btc',Config(balance=args.balance),pairs[1:]),
               ('risk_1pct',Config(balance=args.balance,risk_pct=1,total_risk_pct=2),pairs)]
    args.output_dir.mkdir(parents=True,exist_ok=True)
    summary=[]
    for label,cfg,universe in scenarios:
        for start,end in [(args.start,args.split),(args.split,args.end)]:
            result=replay(data,cfg,timestamp(start),timestamp(end),universe)
            name=label+'_'+start
            result['data_sha256']=hashlib.sha256(raw).hexdigest()
            (args.output_dir/(name+'.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
            row={k:result[k] for k in ['closed_count','closed_net','end_equity',
                  'profit_factor','sampled_equity_max_drawdown','skips']}
            row.update(name=name,open_count=len(result['open_positions']),
                       equity_change=result['end_equity']-args.balance)
            summary.append(row);print(json.dumps(row),flush=True)
    (args.output_dir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__=='__main__':main()
