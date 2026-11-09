import sys,json,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.core import ROOT,Session,Row
with zipfile.ZipFile(sys.argv[1]) as z:
 records=json.loads(z.read('month-records.json'))
 months={r['month'] for r in records}
 if len(months)!=1:raise ValueError('备份月份不一致')
 month=months.pop()
 import re
 if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month):raise ValueError('月份无效')
 allowed={'file','program','job','duplicate','history','resolution','suggestion'}
 # Validate all required source copies before changing the database.
 for r in records:
  if r['kind']=='file':
   name=Path(r['data']['path']).name
   if Path(name).suffix.lower() not in ('.doc','.docx'):raise ValueError('来源格式错误')
   content=z.read('sources/'+name)
   path=ROOT/'sources'/name
   if not path.exists():path.write_bytes(content)
   r['data']['path']=str(path)
 with Session.begin() as db:
  db.query(Row).filter(Row.month==month,Row.kind.in_(allowed)).delete(synchronize_session=False)
  for r in records:
   if r['kind'] not in allowed:continue
   status=r['status']
   if r['kind']=='job' and status=='running':status='queued'
   db.add(Row(id=r['id'],kind=r['kind'],month=month,status=status,version=r['version'],data=json.dumps(r['data'],ensure_ascii=False)))
print('已恢复月份：'+month)
