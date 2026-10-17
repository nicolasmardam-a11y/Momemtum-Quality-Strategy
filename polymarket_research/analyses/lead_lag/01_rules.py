"""Pull resolution rules (description, resolutionSource) for each crypto market family (read-only).
Writes data/derived/lead_lag/crypto_rules_<UTC>.json
"""
import json, re, time, sys
from datetime import datetime, timezone
from pmr import api
ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')
ms = api.gamma_markets(closed='false', end_date_min=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                       end_date_max='2026-10-19T00:00:00Z', max_pages=40)
fam = {}
for m in ms:
    s = m.get('slug', '')
    if not re.search(r'(updown|up-or-down|above|price-of|bitcoin|ethereum)', s):
        continue
    k = re.sub(r'\d{9,}', '<ts>', s)
    k = re.sub(r'(january|february|march|april|may|june|july|august|september|october|november|december)-\d+.*', '<date>', k)
    k = re.sub(r'-\d+(k)?-on', '-<K>-on', k)
    if k in fam:
        fam[k]['n'] += 1
        continue
    fam[k] = dict(n=1, slug=s, question=m.get('question'), description=m.get('description'),
                  resolutionSource=m.get('resolutionSource'), startDate=m.get('startDate'), endDate=m.get('endDate'),
                  eventStartTime=m.get('eventStartTime'), feeType=m.get('feeType'), feeSchedule=m.get('feeSchedule'),
                  tick=m.get('orderPriceMinTickSize'), minsize=m.get('orderMinSize'), negRisk=m.get('negRisk'),
                  umaResolutionStatus=m.get('umaResolutionStatus'), customLiveness=m.get('customLiveness'),
                  rewardsMinSize=m.get('rewardsMinSize'), rewardsMaxSpread=m.get('rewardsMaxSpread'),
                  events_series=[(e.get('seriesSlug'), e.get('slug')) for e in (m.get('events') or [])][:2])
out = f'data/derived/lead_lag/crypto_rules_{ts}.json'
json.dump(fam, open(out, 'w'), indent=1, default=str)
print(out, len(fam))
for k, v in sorted(fam.items(), key=lambda x: -x[1]['n'])[:40]:
    print(v['n'], k)
