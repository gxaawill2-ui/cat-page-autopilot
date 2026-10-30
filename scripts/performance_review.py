"""Read-only Page measurements; persist a non-duplicated review every three days."""
import datetime as dt
import json
import os
import meta_graph_publish as base
import meta_native_schedule as native

ROOT=base.ROOT
ANCHOR=dt.date(2026,10,27)

def completed_period(now):
    index=(now.astimezone(base.TZ).date()-ANCHOR).days//3-1
    if index<0: return None
    start=ANCHOR+dt.timedelta(days=index*3)
    return start,start+dt.timedelta(days=2)

def count(value):
    return value if type(value) is int and value>=0 else None

def row(post,now):
    age=(now-native.stamp(post['created_time'])).total_seconds()/3600
    return {'post_id':post['id'],'created_time':post['created_time'],
            'age_hours':round(age,2),'caption':post.get('message'),
            'reactions':count(post.get('reactions',{}).get('summary',{}).get('total_count')),
            'comments':count(post.get('comments',{}).get('summary',{}).get('total_count')),
            'shares':count(post.get('shares',{}).get('count')),
            'reach':None,'impressions':None,'overseas_share':None,
            'US_reach':None,'JP_reach':None,'PH_reach':None,
            'interactions_per_1000_reach':None,'share_rate':None,
            'attributed_new_followers':None}

def run(now=None):
    now=now or dt.datetime.now(base.TZ)
    period=completed_period(now)
    if not period: return
    start,end=period
    path=ROOT/'records/reviews'/(str(start)+'_'+str(end)+'.json')
    if path.exists():
        print('THREE_DAY_REVIEW_ALREADY_SAVED '+path.name);return
    token=os.environ.get('META_PAGE_ACCESS_TOKEN')
    if not token: raise ValueError('Review requires existing Meta Secret; no write or inference')
    identity= native.api('me',token,{'fields':'id,name'})
    if identity.get('id')!=base.PAGE_ID: raise ValueError('Review wrong Page')
    errors=[]
    followers=None
    try:
        followers=count(native.api('me',token,{'fields':'id,followers_count'}).get('followers_count'))
    except native.Rejected as exc: errors.append(str(exc))
    since=dt.datetime.combine(start,dt.time(),base.TZ)
    until=dt.datetime.combine(end+dt.timedelta(days=1),dt.time(),base.TZ)
    fields='id,message,created_time,is_published,reactions.limit(0).summary(true),comments.limit(0).summary(true),shares'
    try:
        data=native.api(base.PAGE_ID+'/posts',token,{'fields':fields,'since':int(since.timestamp()),'until':int(until.timestamp()),'limit':100})
    except native.Rejected as exc:
        errors.append(str(exc))
        data=native.api(base.PAGE_ID+'/posts',token,{'fields':'id,message,created_time,is_published','since':int(since.timestamp()),'until':int(until.timestamp()),'limit':100})
    if not isinstance(data.get('data'),list) or data.get('paging',{}).get('next'):
        raise ValueError('Incomplete review inventory; do not fabricate measurements')
    rows=[row(p,now) for p in data['data'] if p.get('is_published') is True
          and start<=native.stamp(p['created_time']).date()<=end]
    # Match only actual post IDs; never infer language, audience or image from search results.
    known={}
    for p in (ROOT/'state/meta_native').glob('*.json'):
        old=base.read(p)
        if old.get('meta_post_id') and old.get('slot'): known[old['meta_post_id']]=old
    for r in rows:
        old=known.get(r['post_id'],{})
        slot=old.get('slot','')
        qp=ROOT/'queue/meta'/slot[:10]/(slot[11:].replace(':','')+'.json')
        q=base.read(qp) if slot and qp.exists() else {}
        r.update(language=q.get('language'),topic=q.get('topic'),image_sha256=q.get('image_sha256'))
    mature=[r for r in rows if r['age_hours']>=24]
    previous=[]
    for old_path in (ROOT/'records/reviews').glob('*.json'):
        old=base.read(old_path)
        if old.get('checked_at') and old.get('followers_observed_now') is not None:
            previous.append(old)
    prior=max(previous,key=lambda x:x['checked_at']) if previous else None
    net=(followers-prior['followers_observed_now']) if followers is not None and prior else None
    result={'period_start':str(start),'period_end':str(end),'checked_at':now.isoformat(),
            'page_id':base.PAGE_ID,'followers_observed_now':followers,'new_followers':None,'net_follower_change_since_previous_observation':net,
            'previous_observation_at':prior['checked_at'] if prior else None,
            'posts':rows,'actual_published_samples':len(rows),'mature_samples':len(mature),
            'missing_data_is_zero':False,'errors':errors,'facebook_write_calls':0,'ai_calls':0,
            'sufficient_for_strategy_claim':len(mature)>=8 and not errors and all(r['reach'] is not None for r in mature),
            'decision':'No winner or overseas-growth claim: reach/follower attribution unavailable; preserve controlled trials.',
            'confounding':'Brand, language and frequency changes overlap. Compare equal post ages; never attribute all change to brand or language.',
            'next_review_period_end':str(end+dt.timedelta(days=3))}
    base.write(path,result);base.persist(path,'Save actual three-day Page measurements '+str(end))
    print(json.dumps({'review':path.name,'samples':len(rows),'followers':followers,'errors':errors,'facebook_write_calls':0},ensure_ascii=False))

if __name__=='__main__':
    run()
