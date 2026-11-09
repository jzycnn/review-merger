import zipfile
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
from backend.tests.test_monthly_workflow import record
from backend.app.core import Template
from backend.app.documents import export_word

def test_fixed_typography_removes_hidden_japanese_fonts_and_template_overrides(tmp_path):
 r=record(1,'点评2026年，数字123。')
 out=tmp_path/'fixed.docx'
 export_word([r],'2026-09',out,Template(font='MS Gothic',size=24,line_spacing=2))
 doc=Document(out)
 for p in doc.paragraphs:
  assert p.paragraph_format.line_spacing==1.0
  for run in p.runs:
   assert run.font.size.pt==12
   assert run._element.rPr.rFonts.get(qn('w:eastAsia'))=='宋体'
 with zipfile.ZipFile(out) as z:
  for name in z.namelist():
   if name.startswith('word/') and name.endswith('.xml'):
    blob=z.read(name)
    assert b'MS Gothic' not in blob,name
    root=etree.fromstring(blob)
    for fonts in root.iter(qn('w:rFonts')):
     assert fonts.get(qn('w:eastAsia'))=='宋体'
     assert fonts.get(qn('w:ascii'))=='Times New Roman'

def test_day_separator_between_dates_not_between_same_day_programs(tmp_path):
 a=record(1,'甲点评');b=record(2,'乙点评')
 c={'data':dict(a['data'])};c['data']['program']=dict(a['data']['program'],program_title='同日第二节目')
 out=tmp_path/'days.docx';export_word([b,c,a],'2026-09',out,Template())
 doc=Document(out)
 borders=[p for p in doc.paragraphs if p._p.xpath('./w:pPr/w:pBdr/w:bottom')]
 assert len(borders)==1
 assert not borders[0].text.startswith('2026年9月2日')
 assert doc.paragraphs[next(i for i,p in enumerate(doc.paragraphs) if p._p is borders[0]._p)+1].text=='2026年9月2日《今日评说》审片意见'

def test_format_verification_checks_saved_document(tmp_path):
 from backend.app.documents import verify_export_format
 import pytest
 out=tmp_path/'verified.docx'
 export_word([record(1,'中英文ABC123')],'2026-09',out,Template())
 assert verify_export_format(out)['version']=='fixed-12pt-single-v1'
 doc=Document(out);doc.paragraphs[0].paragraph_format.line_spacing=2;doc.save(out)
 with pytest.raises(ValueError,match='行距'):
  verify_export_format(out)


def test_export_downloads_newest_first_with_distinct_filename(monkeypatch,tmp_path):
 from backend.app import main
 records=[{'id':'old','data':{'created':'2026-11-01'}},{'id':'new','data':{'created':'2026-11-06'}}]
 monkeypatch.setattr(main,'rows',lambda kind,month=None:records if kind=='export' else [])
 assert [r['id'] for r in main.state('2026-10')['export']]==['new','old']
 monkeypatch.setattr(main,'get',lambda id:{'kind':'export','data':{'path':str(tmp_path/'a.docx'),'name':'a.docx','download_name':'fixed_20261106.docx'}})
 response=main.download('new','word')
 assert response.headers['cache-control']=='no-store'
 assert 'fixed_20261106.docx' in response.headers['content-disposition']
