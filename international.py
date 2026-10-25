import datetime as dt,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def plan(slot):
 c=json.loads((ROOT/'state/international.json').read_text()); date,time=slot.split('T'); day=(dt.date.fromisoformat(date)-dt.date.fromisoformat(c['start'])).days+1
 language=c['slots'][time]
 if time=='19:30' and day in c['japanese_trial_days']: language='ja'
 return {'language':language,'target_markets':['TW'] if language=='zh-Hant' else ['JP'] if language=='ja' else ['US','PH'],'experiment_id':c['experiment_id'],'experiment_day':day,'week':1 if day<=7 else 2}
def measures(raw):
 reach=raw.get('reach'); valid=isinstance(reach,(int,float)) and reach>0
 vals=[raw.get(x) for x in ['reactions','comments','shares']]
 return {'reach':reach,'engagement_per_1000_reach':sum(vals)/reach*1000 if valid and all(v is not None for v in vals) else None,'share_rate':raw.get('shares')/reach if valid and raw.get('shares') is not None else None,'overseas_share':None,'US_reach':None,'JP_reach':None,'PH_reach':None,'followers_attributed_to_language':None}
if __name__=='__main__':
 import sys
 print(json.dumps(plan(sys.argv[1]),ensure_ascii=False))
