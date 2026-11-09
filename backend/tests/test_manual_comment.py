from backend.tests.test_workflow import imported,document
from backend.app.core import rows,get,Program
from backend.app.main import app
from fastapi.testclient import TestClient
from docx import Document
from openpyxl import load_workbook
import io
client=TestClient(app)
def record(comment='原稿已有点评'):
 f=imported(document(comment=comment),'20260901.docx')
 return next(r for r in rows('program') if r['data']['file_id']==f)
def test_comment_saved_independently_with_history_and_lock():
 r=record();old=r['data']['blocks']
 # A missing title must not stop saving a draft comment.
 d=r['data'];d['program']['program_title']=None
 from backend.app.core import update
 update(r['id'],d);r=get(r['id'])
 result=client.put('/api/program/'+r['id']+'/comment',json={'version':r['version'],'text':'手填第一段\n手填第二段'})
 assert result.status_code==200,result.text
 saved=result.json();assert saved['data']['editor_comment_manual']=='手填第一段\n手填第二段'
 assert saved['data']['blocks']==old and saved['data']['program']['program_title'] is None
 assert client.get('/api/history/'+r['id']).json()[-1]['data'].get('editor_comment_manual') is None
 assert client.put('/api/program/'+r['id']+'/comment',json={'version':r['version'],'text':'旧版本覆盖'}).status_code==400

def test_manual_comment_exported_once_alongside_source_and_audited():
 r=record();text='手填点评甲\n手填点评乙'
 assert client.put('/api/program/'+r['id']+'/comment',json={'version':r['version'],'text':text}).status_code==200
 result=client.post('/api/export',json={'month':'2026-09','draft':True});assert result.status_code==200,result.text
 paragraphs=[p.text for p in Document(io.BytesIO(client.get(result.json()['word']).content)).paragraphs]
 assert paragraphs.count('手填点评甲')==1 and paragraphs.count('手填点评乙')==1
 assert '原稿已有点评' in paragraphs
 wb=load_workbook(io.BytesIO(client.get(result.json()['audit']).content))
 assert wb['手工填写点评'].cell(2,4).value==text

def test_clear_manual_comment_keeps_original_and_history():
 r=record()
 saved=client.put('/api/program/'+r['id']+'/comment',json={'version':r['version'],'text':'手填内容'}).json()
 cleared=client.put('/api/program/'+r['id']+'/comment',json={'version':saved['version'],'text':''})
 assert cleared.status_code==200
 assert cleared.json()['data']['editor_comment_manual']==''
 assert any(b['original_text']=='原稿已有点评' for b in cleared.json()['data']['blocks'])
 assert any(h['data'].get('editor_comment_manual')=='手填内容' for h in client.get('/api/history/'+r['id']).json())

def test_standard_save_includes_manual_draft():
 r=record('')
 result=client.put('/api/program/'+r['id'],json={'version':r['version'],'program':r['data']['program'],'editor_comment_manual':'本次填写'})
 assert result.status_code==200 and get(r['id'])['data']['editor_comment_manual']=='本次填写'
