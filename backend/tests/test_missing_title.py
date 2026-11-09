import pytest
from backend.app.core import Block,Template
from backend.app.documents import parse,validate,section_label,export_word
from docx import Document

def blocks(lines):return [Block(source_file_id='f',source_block_id=f'f:{i}',original_text=t).model_dump() for i,t in enumerate(lines)]
@pytest.mark.parametrize('label',['领导意见','一、领导意见：','领导审片意见','审片意见','一、审片意见','《领导意见》','《审片意见》','节目标题：'])
def test_missing_title_stays_null(label):
 b=blocks(['2026年10月1日《今日评说》审片意见',label,'二、记者体会','原始体会','三、主编点评','审片人员：张三'])
 result=parse(b,'daily.docx')
 assert result.programs[0].program_title is None
 assert '缺少节目名称' in validate(result,b,'daily.docx')
 assert not any('覆盖' in i for i in validate(result,b,'daily.docx'))
@pytest.mark.parametrize('title',['街头演艺新政 艺术与烟火如何共生','《城市治理如何破题》'])
def test_real_titles_preserved(title):
 b=blocks(['2026年10月1日《今日评说》审片意见',title,'一、领导意见','保留意见'])
 assert parse(b,'daily.docx').programs[0].program_title==title.strip('《》')
def test_no_invented_title_in_draft(tmp_path):
 b=blocks(['2026年10月1日《今日评说》审片意见','一、领导意见','原文意见'])
 p=parse(b,'daily.docx').programs[0]
 path=tmp_path/'draft.docx'
 export_word([{'data':{'program':p.model_dump(),'blocks':b}}],'2026-10',path,Template(),True)
 assert not any(p.style.name=='Heading 2' for p in Document(path).paragraphs)
