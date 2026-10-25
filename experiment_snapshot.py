import json,datetime as dt
from pathlib import Path
import international as intl
ROOT=Path(__file__).resolve().parent
now=dt.datetime.now(dt.timezone.utc)
states={d.get('post_id'):d for p in (ROOT/'state/posts').glob('*.json') if (d:=json.loads(p.read_text())).get('post_id')}
raw=json.loads((ROOT/'records/insights/2026-10-25-posts.json').read_text())
rows=[]
for x in raw['data']:
 s=states.get(x['post_id'],{}); created=dt.datetime.fromisoformat(x['post_created_time']);age=(now-created).total_seconds()/3600
 metrics=intl.measures({'reach':None,'reactions':x.get('post_reactions_total'),'comments':x.get('post_comments_with_reply'),'shares':x.get('post_activity_by_action_type_share')})
 rows.append({'post_id':x['post_id'],'language':s.get('language'),'target_markets':s.get('target_markets'),'experiment_id':s.get('experiment_id'),'observed_at':x.get('data_fetched_at'),'age_hours_at_snapshot':(dt.datetime.fromisoformat(x['data_fetched_at']).replace(tzinfo=dt.timezone.utc)-created).total_seconds()/3600,'viewers':x.get('post_total_media_view_unique'),'views_source_metric':{'post_impressions':x.get('post_impressions')},'metrics':metrics,'source':'records/insights/2026-10-25-posts.json'})
report={'created_at':now.isoformat(),'baseline_only':True,'experiment_results':None,'reason':'International experiment not started; no country reach or per-language follower attribution available. Preserve viewers separately from reach.','observations':rows,'review_due':['2026-11-01','2026-11-08'],'next':'Future runs load their newly saved raw snapshot, retain original observed_at and compare only same-age cohorts. No historical language guessed.'}
p=ROOT/'records/experiments/intl-baseline-2026-10-25.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'rows':len(rows),'international_results':None,'facebook_write_calls':0}))
