from backend.tests.test_workflow import imported,document
from backend.app.core import rows,get,Template
from backend.app.documents import export_word
from backend.app.main import app
from fastapi.testclient import TestClient
from docx import Document
import io
client=TestClient(app)
def record(day=1,comment=''):
 f=imported(document(day,comment=comment),f'202609{day:02}.docx')
 return next(r for r in rows('program') if r['data']['file_id']==f)
def test_editor_heading_always_exists_even_template_hides_missing(tmp_path):
 r=record();r['data']['program']['sections']=[s for s in r['data']['program']['sections'] if s['type']!='editor_comment']
 path=tmp_path/'draft.docx';export_word([r],'2026-09',path,Template(show_missing=False),True)
 assert '三、责编有话说' in [p.text for p in Document(path).paragraphs]
def test_empty_comment_blocks_formal_but_not_draft():
 r=record();body={'program':r['data']['program'],'version':r['version'],'confirmed':True}
 assert client.put('/api/program/'+r['id'],json=body).status_code==200
 result=client.post('/api/export',json={'month':'2026-09'})
 assert result.status_code==400 and '责编有话说尚未填写' in result.json()['detail']
 assert client.post('/api/export',json={'month':'2026-09','draft':True}).status_code==200

def test_corrected_dates_but_original_times_in_single_merged_word():
 first=record(1,'第一期点评');second=record(2,'第二期点评')
 p=first['data']['program'];p.update(review_date='2026-09-03',review_start='16:10',review_end='16:30')
 assert client.put('/api/program/'+first['id'],json={'program':p,'version':first['version'],'confirmed':True}).status_code==200
 assert client.put('/api/program/'+second['id'],json={'program':second['data']['program'],'version':second['version'],'confirmed':True}).status_code==200
 result=client.post('/api/export',json={'month':'2026-09'});assert result.status_code==200,result.text
 doc=Document(io.BytesIO(client.get(result.json()['word']).content));text='\n'.join(p.text for p in doc.paragraphs)
 assert text.index('2026年9月2日《今日评说》审片意见')<text.index('2026年9月3日《今日评说》审片意见')
 assert '2026年9月1日《今日评说》审片意见' not in text
 assert '审片开始时间：15:30 结束时间：15:45' in text
 assert '16:10' not in text and '16:30' not in text
 assert '第一期点评' in text and '第二期点评' in text
 assert any('15:30' in b['original_text'] for b in get(first['id'])['data']['blocks'])

def test_no_invented_time_when_original_has_no_time(tmp_path):
 r=record(1,'点评')
 removed={b['source_block_id'] for b in r['data']['blocks'] if '审片开始时间' in b['original_text']}
 r['data']['blocks']=[b for b in r['data']['blocks'] if b['source_block_id'] not in removed]
 p=r['data']['program'];p['metadata_ids']=[bid for bid in p['metadata_ids'] if bid not in removed]
 p.update(review_start='18:00',review_end='18:20')
 path=tmp_path/'added-time.docx';export_word([r],'2026-09',path,Template())
 text='\n'.join(p.text for p in Document(path).paragraphs)
 assert '18:00' not in text and '18:20' not in text
