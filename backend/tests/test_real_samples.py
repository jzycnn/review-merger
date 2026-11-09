from pathlib import Path
import io
import pytest
from backend.app.core import *
from backend.app.documents import *
from backend.app.worker import ingest,process
SAMPLES=Path(__file__).resolve().parents[2]/'samples'
MASTER=SAMPLES/'《今日评说》9月审片意见.docx'
DAILY=SAMPLES/'2026年9月1日《今日评说》审片意见：《街头演艺新政》.docx'
@pytest.mark.skipif(not MASTER.exists(),reason='真实样本未提供')
def test_actual_styles_and_programs():
    style=analyze_template(MASTER)
    assert style['page_cm']==[21.0,29.7]
    assert style['margins_cm']==[2.54,2.54,3.17,3.17]
    b=read(MASTER,'actual-master');rec=parse(b,MASTER.name)
    assert len(rec.programs)==17
    assert all(p.review_date for p in rec.programs)
    assert not any('覆盖' in i or '归属' in i for i in validate(rec,b,MASTER.name))
    assert next(p for p in rec.programs if p.review_date=='2026-09-29').program_title=='三金二银  浙江选手何以刷新最好成绩'
@pytest.mark.skipif(not DAILY.exists(),reason='真实样本未提供')
def test_actual_daily_blank_comment_and_composite():
    b=read(DAILY,'actual-daily');rec=parse(b,DAILY.name);p=rec.programs[0]
    assert len(b)==9 and len(rec.programs)==1
    assert p.sections[0].original_heading=='一、修改意见及程主任点评'
    assert p.sections[-1].source_block_ids==[]
    assert '复合栏目责任主体需核对' in validate(rec,b,DAILY.name)
@pytest.mark.skipif(not MASTER.exists() or not DAILY.exists(),reason='真实样本未提供')
def test_actual_incremental_preserves_master():
    month='2026-09'
    f=ingest(MASTER.read_bytes(),MASTER.name,month,'master')
    for j in rows('job',month):
        if j['data']['file_id']==f and j['status']=='queued':process(j)
    before=[r for r in rows('program',month) if r['data']['file_id']==f]
    f2=ingest(DAILY.read_bytes(),DAILY.name,month,'daily')
    for j in rows('job',month):
        if j['data']['file_id']==f2 and j['status']=='queued':process(j)
    candidate=next(r for r in rows('program',month) if r['data']['file_id']==f2)
    assert candidate['status']=='conflict'
    master=get(candidate['data']['conflict_with'])
    assert master['data']['origin']=='master'
    sec=next(s for s in master['data']['program']['sections'] if s['type']=='editor_comment')
    assert sec['source_block_ids']
    assert len(before)==17
    assert all(get(r['id'])['data']==r['data'] for r in before)
