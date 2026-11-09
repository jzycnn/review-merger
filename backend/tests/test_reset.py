import json,zipfile
from backend.app.core import rows,put,get,ROOT,Session,Row
from backend.app.reset import request_reset,execute_reset,pending_resets
from backend.tests.test_workflow import imported,document
from backend.app.main import app
from fastapi.testclient import TestClient
client=TestClient(app)
def test_restart_preserves_sources_other_month_and_exports():
 f=imported(document(),'20260901.docx');original=get(f)['data'];path=original['path']
 other=put('program',{'untouched':True},'2026-10')
 export=put('export',{'name':'历史导出'},'2026-09')
 command=request_reset('2026-09','restart');execute_reset(command['id'])
 assert not rows('program','2026-09')
 assert get(other)['data']=={'untouched':True} and get(export)['data']['name']=='历史导出'
 assert get(f)['status']=='queued' and get(f)['data']['path']==path
 from pathlib import Path
 assert Path(path).is_file()
 jobs=rows('job','2026-09');assert len(jobs)==1 and jobs[0]['status']=='queued'
 result=get(command['id']);assert result['status']=='done'
 with zipfile.ZipFile(result['data']['backup']) as z:
  saved=json.loads(z.read('month-records.json'))
  assert any(r['kind']=='program' for r in saved)
  assert any(name.startswith('sources/') for name in z.namelist())
 from backend.app.worker import process
 process(jobs[0]);assert len(rows('program','2026-09'))==1

def test_clear_empties_list_and_pauses_watch():
 f=imported(document(),'daily.docx');put('active_month',{'month':'2026-09'})
 command=request_reset('2026-09','clear');execute_reset(command['id'])
 assert not rows('file','2026-09') and not rows('program','2026-09') and not rows('job','2026-09')
 assert not rows('active_month')
 from pathlib import Path
 assert list((ROOT/'sources').glob('*.docx'))

def test_backup_failure_preserves_every_record():
 f=imported(document(),'daily.docx')
 d=get(f)['data'];d['path']=str(ROOT/'missing.docx')
 from backend.app.core import update
 update(f,d);before=rows('program','2026-09')
 command=request_reset('2026-09','clear');pending_resets()
 assert get(command['id'])['status']=='failed'
 assert rows('program','2026-09')==before and get(f)

def test_confirmation_required_and_duplicate_commands_deduplicated():
 imported(document(),'daily.docx')
 assert client.post('/api/reset',json={'month':'2026-09'}).status_code==400
 body={'month':'2026-09','confirm_month':'2026-09','mode':'restart'}
 a=client.post('/api/reset',json=body);b=client.post('/api/reset',json=body)
 assert a.status_code==200 and a.json()['id']==b.json()['id']

def test_reset_repeated_processing_no_duplicate_jobs():
 imported(document(),'daily.docx')
 command=request_reset('2026-09','restart')
 execute_reset(command['id']);execute_reset(command['id'])
 assert len(rows('job','2026-09'))==1

def test_month_backup_restore_roundtrip():
 import subprocess,sys,os
 from pathlib import Path
 f=imported(document(),'daily.docx');before=rows('program','2026-09')
 command=request_reset('2026-09','clear');execute_reset(command['id'])
 script=Path(__file__).resolve().parents[2]/'scripts'/'restore_month.py'
 result=subprocess.run([sys.executable,str(script),get(command['id'])['data']['backup']],capture_output=True,env=dict(os.environ,REVIEW_HOME=str(ROOT)))
 assert result.returncode==0,result.stderr
 assert get(f)['status']=='success' and rows('program','2026-09')==before
