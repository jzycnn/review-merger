import pytest
from pathlib import Path
from backend.app.documents import read,parse,validate
from backend.app.core import Recognition,rows,ROOT
from backend.app.doc_binary import WARNING,extract_text
from backend.tests.test_workflow import imported
SAMPLE=Path(__file__).resolve().parents[2]/'samples'/'20260929《今日评说》审片意见.doc'
@pytest.mark.skipif(not SAMPLE.exists(),reason='公开版不包含真实审片资料')
def test_real_doc_without_word(monkeypatch):
    import backend.app.documents as docs
    monkeypatch.setattr(docs,'convert',lambda p:(_ for _ in ()).throw(RuntimeError('Word unavailable')))
    b=read(SAMPLE,'doc-test');result=parse(b,SAMPLE.name);p=result.programs[0]
    assert p.review_date=='2026-09-29'
    assert p.program_title=='三金二银  浙江选手何以刷新最好成绩'
    bm={v['source_block_id']:v['original_text'] for v in b}
    assert [bm[i] for i in p.sections[0].source_block_ids]==['1，无']
    assert len(p.sections[1].source_block_ids)==2
    assert p.sections[2].source_block_ids==[]
    assert p.review_start=='17:05' and p.review_end=='17:20'
    assert WARNING in validate(result,b,SAMPLE.name)
    assert not any('覆盖' in i or '重复' in i for i in validate(result,b,SAMPLE.name))
def test_corrupt_doc_fails(tmp_path):
    p=tmp_path/'broken.doc';p.write_bytes(b'broken')
    with pytest.raises(Exception):extract_text(p)
@pytest.mark.skipif(not SAMPLE.exists(),reason='公开版不包含真实审片资料')
def test_doc_incremental_preserves_master(monkeypatch):
    import backend.app.documents as docs
    original_convert=docs.convert
    def native_doc(path):
        if path.suffix.lower()=='.doc':raise RuntimeError('native DOC regression: Word intentionally unavailable')
        return original_convert(path)
    monkeypatch.setattr(docs,'convert',native_doc)
    master=SAMPLE.parent/'《今日评说》9月审片意见.docx'
    f=imported(master.read_bytes(),master.name,role='master')
    before=[r for r in rows('program') if r['data']['file_id']==f]
    new=imported(SAMPLE.read_bytes(),SAMPLE.name)
    candidate=next(r for r in rows('program') if r['data']['file_id']==new)
    assert candidate['status']=='conflict'
    from backend.app.core import get
    assert all(get(r['id'])['data']==r['data'] for r in before)
