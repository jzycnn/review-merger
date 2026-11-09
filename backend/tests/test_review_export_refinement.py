from backend.tests.test_workflow import imported,document
from backend.app.core import rows,get,Template
from backend.app.documents import export_word
from backend.app.main import app
from fastapi.testclient import TestClient
from docx import Document
from docx.oxml.ns import qn
client=TestClient(app)
def record():
 f=imported(document(comment='原稿点评'),'20260901.docx')
 return next(r for r in rows('program') if r['data']['file_id']==f)
def test_review_confirm_keeps_latest_saved_comment_and_source_times():
 r=record();saved=client.put('/api/program/'+r['id']+'/comment',json={'version':r['version'],'text':'第二步保存的点评'}).json()
 p=saved['data']['program'];p['program_title']='核对后标题';p['review_start']='19:00';p['review_end']='19:20'
 response=client.put('/api/program/'+r['id'],json={'version':saved['version'],'program':p,'confirmed':True,'acknowledge':True})
 assert response.status_code==200,response.text
 latest=get(r['id']);assert latest['data']['editor_comment_manual']=='第二步保存的点评'
 assert latest['data']['program']['review_start']=='15:30' and latest['data']['program']['review_end']=='15:45'
 assert latest['status']=='verified'
def test_export_no_original_heading_note_and_fonts_correct(tmp_path):
 r=record();r['data']['program']['sections'][0]['original_heading']='一、修改意见及程主任点评'
 r['data']['editor_comment_manual']='点评2026年，有123个例子。'
 path=tmp_path/'fonts.docx';export_word([r],'2026-09',path,Template(font='黑体'))
 doc=Document(path);texts=[p.text for p in doc.paragraphs]
 assert not any('原栏目' in t for t in texts)
 assert '点评2026年，有123个例子。' in texts
 for para in doc.paragraphs:
  for run in para.runs:
   fonts=run._element.rPr.rFonts
   assert fonts.get(qn('w:eastAsia'))=='宋体'
   assert fonts.get(qn('w:ascii'))=='Times New Roman'
   assert fonts.get(qn('w:hAnsi'))=='Times New Roman'
 assert any('15:30' in t for t in texts)
