#!/usr/bin/env python3
"""Build an evidence-aware weekly snapshot. Never replace absent metrics with zero."""
import datetime as dt,json,statistics,sys
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent
TZ=ZoneInfo('Asia/Taipei')
METRICS=['post_impressions','post_total_media_view_unique','post_views','post_reactions_total','post_reactions_no_shares','post_comments_with_reply','post_activity_by_action_type_share']
def build(posts,page,at):
    data=posts['data']; cutoff=at.replace(hour=0,minute=0,second=0,microsecond=0); prior_end=cutoff-dt.timedelta(days=7); start=cutoff-dt.timedelta(days=14); mature=at-dt.timedelta(hours=48)
    states={x['post_id']:x for p in (ROOT/'state/posts').glob('*.json') if (x:=json.loads(p.read_text())).get('post_id')}
    rows=[]
    for raw in data:
        t=dt.datetime.fromisoformat(raw['post_created_time']).astimezone(TZ)
        if not start<=t<cutoff: continue
        known=states.get(raw['post_id'],{})
        rows.append({'post_id':raw['post_id'],'created_at':t.isoformat(),'topic':known.get('topic'),'style':known.get('style'),'caption_type':known.get('caption_type'),'classification':'recorded' if known else 'unknown','caption_length':len(raw.get('post_message') or ''),'time_bucket':'noon' if 11<=t.hour<15 else 'evening' if 18<=t.hour<22 else 'other','mature_48h':t<=mature,'window':'recent' if t>=prior_end else 'prior','is_transport_test':'圖片網址發布測試' in (raw.get('post_message') or ''),'metrics':{k:raw.get(k) for k in METRICS},'post_url':raw.get('permalink_url'),'data_fetched_at':raw.get('data_fetched_at')})
    def summary(rs):
        return {'n':len(rs),**{k:{'reported_sum':sum(v) if (v:=[r['metrics'][k] for r in rs if r['metrics'][k] is not None]) else None,'reported_median':statistics.median(v) if v else None,'missing':sum(r['metrics'][k] is None for r in rs),'zeros':sum(r['metrics'][k]==0 for r in rs)} for k in METRICS}}
    eligible=[r for r in rows if r['mature_48h'] and not r['is_transport_test']]
    recent=[r for r in eligible if r['window']=='recent'];prior=[r for r in eligible if r['window']=='prior']
    ranked=sorted(recent,key=lambda r:(r['metrics']['post_impressions'] is not None,r['metrics']['post_impressions'] or 0),reverse=True)
    history=list((ROOT/'records/reviews').glob('*.json'))
    return {'generated_at':at.isoformat(),'period_days':14,'rows':rows,'recent_mature':summary(recent),'prior_mature':summary(prior),'ranking_metric':'reported post_impressions; descriptive only','top5_ids':[r['post_id'] for r in ranked[:5]],'bottom5_ids':[r['post_id'] for r in ranked[-5:]],'data_quality':{'reach':'suspect; new post_total_media_view_unique also returns 1–2 on older posts; Meta Suite comparison required','page_follows':'connector reports zero; do not substitute for unavailable data','missing_kept_null':True,'style_comparison':'older image style unknown, cannot attribute differences'},'conclusions':{'best_topic':None,'best_image_style':None,'best_shareable_caption':None,'best_time':None,'follower_growth':None,'reason':'No comparable prior mature window; insufficient labelled samples; suspect reach.'},'improvement_rules':{'elapsed_days_supported_by_snapshots':0 if not history else None,'7_day':'check publishing, source completeness, reach limitations, then single-variable experiments','14_day':'broaden subjects/styles/formats only with comparable evidence','30_day':'positioning review only after 30 days and >=5 mature posts per comparison group','triggered':False,'reason':'first persisted V3 snapshot; no invented historical trend'},'next_experiments':[{'variable':'caption_type','levels':['short_humor','short_story'],'hold_constant':['topic','image_style','time_bucket'],'min_mature_posts_per_level':5},{'variable':'image_style','levels':['warm_illustration','natural_realism'],'hold_constant':['topic','caption_type','time_bucket'],'min_mature_posts_per_level':5}],'page_daily':page['data']}
if __name__=='__main__':
    day=sys.argv[1];posts=json.loads((ROOT/f'records/insights/{day}-posts.json').read_text());page=json.loads((ROOT/f'records/insights/{day}-page.json').read_text())
    result=build(posts,page,dt.datetime.now(TZ));p=ROOT/f'records/reviews/{day}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['generated_at','recent_mature','prior_mature','conclusions']},ensure_ascii=False))
