import os, tempfile, io
os.environ['REVIEW_HOME']=tempfile.mkdtemp(prefix='review-test-')
from docx import Document
from backend.app.core import *
from backend.app.documents import *
from backend.app.worker import ingest,process
from backend.app.main import app
from fastapi.testclient import TestClient
client=TestClient(app)
def document(day=1,title='街头演艺新政',comment='',opinion='无'):
    doc=Document()
    for line in [f'2026年9月{day}日《今日评说》审片意见',f'《{title}》','一、修改意见',opinion,'二、记者体会','第一段体会。','第二段体会，保留数字123。','五、主编点评',comment,'审片开始时间：15:30 结束时间：15:45','审片人员：张三、李四']:
        doc.add_paragraph(line)
    f=io.BytesIO();doc.save(f);return f.getvalue()
def imported(content,name,month='2026-09',role='daily'):
    fid=ingest(content,name,month,role)
    for j in rows('job',month):
        if j['data']['file_id']==fid and j['status']=='queued':process(j)
    return fid

def test_roundtrip_preserve():
    fid=imported(document(), '20260901.docx')
    r=next(r for r in rows('program','2026-09') if r['data']['file_id']==fid)
    p=Program.model_validate(r['data']['program']);assert p.review_date=='2026-09-01'
    assert p.program_title=='街头演艺新政'
    assert p.sections[2].source_block_ids==[]
    assert not validate(Recognition(programs=[p]),r['data']['blocks'],'20260901.docx')
    path=ROOT/'roundtrip.docx';export_word([r],'2026-09',path,Template())
    text='\n'.join(p.text for p in Document(path).paragraphs)
    assert '无' in text and '第二段体会，保留数字123。' in text

def test_master_not_overwritten_and_conflict():
    imported(document(2,comment='母稿补充点评'), '母稿.docx',role='master')
    imported(document(2), '20260902.docx')
    records=[r for r in rows('program','2026-09') if r['data']['program']['review_date']=='2026-09-02']
    assert len(records)==2
    master=next(r for r in records if r['data']['origin']=='master')
    assert any(b['original_text']=='母稿补充点评' for b in master['data']['blocks'])
    candidate=next(r for r in records if r['status']=='conflict')
    assert client.post('/api/resolve/'+candidate['id'],json={'action':'keep'}).status_code==200
    assert get(master['id'])['status']!='superseded'

def test_deduplicate():
    n=len(rows('file'));a=ingest(document(3),'a.docx','2026-09','daily');b=ingest(document(3),'b.docx','2026-09','daily')
    assert a==b and len(rows('file'))==n+1

def test_body_filename_conflict():
    fid=imported(document(4),'20260905.docx');r=get(fid)
    assert '正文与文件名日期冲突' in r['data']['issues']

def test_unknown_source_rejected():
    p=Program(metadata_ids=['invented'])
    import pytest
    with pytest.raises(ValueError):validate(Recognition(programs=[p]),[],'')

def test_export_block_and_draft():
    imported(document(6),'20260906.docx')
    assert client.post('/api/export',json={'month':'2026-09'}).status_code==400
    r=client.post('/api/export',json={'month':'2026-09','draft':True})
    assert r.status_code==200,r.text
    assert client.get(r.json()['word']).status_code==200
    assert client.get(r.json()['audit']).status_code==200

def test_revision_and_optimistic_lock():
    imported(document(8),'20260908.docx')
    r=next(r for r in rows('program') if r['status']=='ready')
    p=r['data']['program'];p['program_title']='核对后标题'
    assert client.put('/api/program/'+r['id'],json={'program':p,'version':r['version']}).status_code==200
    assert len(client.get('/api/history/'+r['id']).json())>=1
    assert client.put('/api/program/'+r['id'],json={'program':p,'version':r['version']}).status_code==400

def test_two_programs_one_day():
    doc=Document(io.BytesIO(document(7,title='节目甲')))
    other=Document(io.BytesIO(document(7,title='节目乙')))
    for p in other.paragraphs:doc.add_paragraph(p.text)
    stream=io.BytesIO();doc.save(stream);fid=imported(stream.getvalue(),'20260907.docx')
    assert get(fid)['data']['program_count']==2

def test_missing_and_unclassified():
    b=[Block(source_file_id='f',source_block_id='b',original_text='未标注原文').model_dump()]
    result=parse(b,'unknown.docx');issues=validate(result,b,'unknown.docx')
    assert '缺少日期' in issues and '缺少节目名称' in issues and '存在未归类原文' in issues

def test_cross_site_denied():
    assert client.post('/api/scan',json={'month':'2026-09'},headers={'origin':'https://evil.invalid'}).status_code==403

def test_invalid_month():
    assert client.get('/api/state?month=../../x').status_code==400

def test_schema_rejects_invalid_type():
    import pytest
    with pytest.raises(Exception):Section(type='invented')
