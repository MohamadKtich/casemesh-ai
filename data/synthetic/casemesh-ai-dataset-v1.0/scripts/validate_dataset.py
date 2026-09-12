from __future__ import annotations
import csv, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
customers={}
with open(ROOT/'reference/customers.csv',encoding='utf-8') as f:
    for r in csv.DictReader(f): customers[r['customer_id']]=r
# evidence refs
for p in list((ROOT/'cases').glob('*.json'))+list((ROOT/'evaluation').glob('*.json')):
    d=json.loads(p.read_text(encoding='utf-8'))
    for rel in d.get('evidence_files',[]):
        if not (ROOT/rel).exists(): errors.append(f'{p.name}: missing {rel}')
# monthly formula
for p in (ROOT/'telemetry/monthly_sla_metrics').glob('*.csv'):
    with open(p,encoding='utf-8') as f: r=next(csv.DictReader(f))
    calc=(int(r['total_billable_minutes'])-int(r['covered_downtime_minutes']))/int(r['total_billable_minutes'])*100
    if abs(calc-float(r['monthly_uptime_pct']))>1e-5: errors.append(f'{p.name}: uptime mismatch')
if errors:
    print('\n'.join(errors)); raise SystemExit(1)
print('VALIDATION_OK')
