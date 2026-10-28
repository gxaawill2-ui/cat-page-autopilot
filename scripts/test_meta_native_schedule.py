import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import meta_native_schedule as n

class NativeSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.p=patch.object(n,"ROOT",self.root);self.p.start()
        self.quiet=patch("builtins.print");self.quiet.start()
        n.base.write(self.root/'state/policy.json',{"mode":"live","page_id":n.PAGE,"timezone":"Asia/Taipei","daily_limit":4})
        self.planned=(dt.datetime.now(n.TZ)+dt.timedelta(days=1)).replace(hour=19,minute=30,second=0,microsecond=0)
        self.q={"page_id":n.PAGE,"slot":self.planned.strftime('%Y-%m-%dT%H:%M'),"caption":"An entirely new cat adventure.","language":"en","image_sha256":"a"*64,"image_url":n.base.ASSET_BASE+"a"*64+".jpg","image_qa":True}
        self.now=self.planned-dt.timedelta(hours=2)
    def tearDown(self):
        self.quiet.stop();self.p.stop();self.tmp.cleanup()
    def save(self,path,value,message):
        n.base.write(path,value)
    def api(self,path,token,params=None,method="GET"):
        if path=='me':return {"id":n.PAGE}
        if path.endswith('/posts') or path.endswith('/scheduled_posts'):return {"data":[]}
        if method=='POST' and path.endswith('/photos'):return {"id":"8877"}
        if method=='POST' and path.endswith('/feed'):return {"id":n.PAGE+'_9988'}
        return {"id":n.PAGE+'_9988',"message":self.q['caption'],"is_published":False,"scheduled_publish_time":int(self.planned.timestamp()),"full_picture":"https://example.invalid/photo","attachments":{"data":[{"target":{"id":"8877"}}]}}
    def test_past_is_rejected(self):
        with self.assertRaises(ValueError):n.validate(self.q,self.planned+dt.timedelta(seconds=1))
    def test_short_lead_rejected(self):
        with self.assertRaises(ValueError):n.validate(self.q,self.planned-dt.timedelta(minutes=14))
    def test_over_three_days_rejected(self):
        with self.assertRaises(ValueError):n.validate(self.q,self.planned-dt.timedelta(days=4))
    def test_wrong_page_rejected(self):
        self.q['page_id']='1'
        with self.assertRaises(ValueError):n.validate(self.q,self.now)
    def test_visual_qa_required(self):
        self.q['image_qa']=False
        with self.assertRaises(ValueError):n.validate(self.q,self.now)
    def test_only_canonical_queue_paths(self):
        for x in ['../../secret','queue/meta/2026-10-29/0000.json','queue/meta/2026-10-29/0930.json;echo bad']:
            with self.assertRaises(ValueError):n.queue_file(x)
    def test_historical_queued_image_blocked(self):
        n.base.write(self.root/'queue/meta/2026-10-28/1930.json',{**self.q,'slot':'2026-10-28T19:30'})
        with self.assertRaises(ValueError):n.validate(self.q,self.now)
    def test_armed_slot_never_replayed(self):
        n.base.write(n.record_file(self.q),{'status':'schedule_armed_unknown'})
        with self.assertRaises(ValueError):n.validate(self.q,self.now)
    def test_four_unknown_attempts_consume_daily_cap(self):
        for i in range(4):
            n.base.write(self.root/f'state/meta_native/x{i}.json',{'slot':self.planned.strftime('%Y-%m-%d')+f'T{9+i:02}:30','status':'schedule_armed_unknown'})
        with self.assertRaises(ValueError):n.remote_guard(self.q,self.planned,4,{'posts':[],'scheduled_posts':[]})
    def test_remote_native_slot_is_occupied(self):
        with self.assertRaises(ValueError):n.remote_guard(self.q,self.planned,4,{'posts':[],'scheduled_posts':[{'id':'other','scheduled_publish_time':int(self.planned.timestamp())}]})
    def test_cas_failure_before_upload_prevents_every_post(self):
        with patch.object(n,'api',side_effect=self.api) as call,patch.object(n.base,'verify_image'),patch.object(n,'save',side_effect=RuntimeError('CAS failed')):
            with self.assertRaises(RuntimeError):n.schedule(self.q,'fixture',self.now)
            self.assertFalse(any(c.kwargs.get('method')=='POST' for c in call.call_args_list))
    def test_unknown_upload_is_not_replayed(self):
        def unknown(path,token,params=None,method='GET'):
            if method=='POST':raise TimeoutError('unknown')
            return self.api(path,token,params,method)
        with patch.object(n,'api',side_effect=unknown) as call,patch.object(n.base,'verify_image'),patch.object(n,'save',side_effect=self.save):
            with self.assertRaises(TimeoutError):n.schedule(self.q,'fixture',self.now)
            with self.assertRaises(ValueError):n.schedule(self.q,'fixture',self.now)
            self.assertEqual(sum(c.kwargs.get('method')=='POST' for c in call.call_args_list),1)
    def test_unpublished_photo_then_scheduled_feed(self):
        with patch.object(n,'api',side_effect=self.api) as call,patch.object(n.base,'verify_image'),patch.object(n,'save',side_effect=self.save):
            result=n.schedule(self.q,'fixture',self.now)
            writes=[c for c in call.call_args_list if c.kwargs.get('method')=='POST']
            self.assertEqual(len(writes),2)
            self.assertTrue(all(c.args[2]['published']=='false' for c in writes))
            feed=writes[1].args[2]
            self.assertEqual(feed['unpublished_content_type'],'SCHEDULED')
            self.assertEqual(json.loads(feed['attached_media[0]']),{'media_fbid':'8877'})
            self.assertEqual(result['status'],'scheduled_api_verified')
            self.assertFalse(result['readback']['is_published'])
    def test_photo_id_is_not_a_post_id(self):
        def bad_feed(path,token,params=None,method='GET'):
            if method=='POST' and path.endswith('/feed'):return {'id':'8877'}
            return self.api(path,token,params,method)
        with patch.object(n,'api',side_effect=bad_feed),patch.object(n.base,'verify_image'),patch.object(n,'save',side_effect=self.save):
            with self.assertRaises(ValueError):n.schedule(self.q,'fixture',self.now)
            self.assertEqual(n.load(n.record_file(self.q))['status'],'schedule_armed_unknown')
    def test_explicit_feed_rejection_saved_without_retry(self):
        def denied(path,token,params=None,method='GET'):
            if method=='POST' and path.endswith('/feed'):raise n.Rejected('Meta HTTP 400: code 100')
            return self.api(path,token,params,method)
        with patch.object(n,'api',side_effect=denied),patch.object(n.base,'verify_image'),patch.object(n,'save',side_effect=self.save):
            with self.assertRaises(n.Rejected):n.schedule(self.q,'fixture',self.now)
            self.assertEqual(n.load(n.record_file(self.q))['status'],'schedule_rejected')

if __name__=='__main__':unittest.main()
