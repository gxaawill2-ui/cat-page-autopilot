import datetime as dt,json
from pathlib import Path
from zoneinfo import ZoneInfo
def review_key(at):
 at=at.astimezone(ZoneInfo('Asia/Taipei'));start=dt.date(2026,10,29);days=(at.date()-start).days
 if days<0 or (days%3==0 and at.time()<dt.time(19,30)):return None
 due=start+dt.timedelta(days=(days//3)*3)
 return due.isoformat()
def due(at,root):
 key=review_key(at)
 return key if key and not (Path(root)/'records/reviews'/('cycle-'+key+'.json')).exists() else None
if __name__=='__main__':print(json.dumps({'due_key':due(dt.datetime.now(dt.timezone.utc),Path(__file__).parent)}))
