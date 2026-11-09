import io

import pytest
from docx import Document

from backend.app.core import get, rows
from backend.tests.test_workflow import document, imported


def changed_document(old, new):
    doc = Document(io.BytesIO(document(comment='示例责编点评')))
    for paragraph in doc.paragraphs:
        if old in paragraph.text:
            paragraph.text = paragraph.text.replace(old, new)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


@pytest.mark.parametrize('label', ['主任点评', '一、主任点评：', '程主任点评'])
def test_standalone_director_comment_is_review_opinion(label):
    file_id = imported(changed_document('一、修改意见', label), '不同栏目.docx')
    record = next(r for r in rows('program') if r['data']['file_id'] == file_id)
    section = record['data']['program']['sections'][0]
    assert section['type'] == 'review_opinion'
    assert section['original_heading'] == label
    assert not record['data']['issues']


@pytest.mark.parametrize(('old', 'new'), [
    ('结束时间：15:45', '结束时间：16:00'),
    ('审片人员：张三、李四', '审片人员：张三、王五'),
])
def test_changed_metadata_creates_conflict_without_overwriting_master(old, new):
    master_id = imported(document(comment='示例责编点评'), '月度母稿.docx', role='master')
    master = next(r for r in rows('program') if r['data']['file_id'] == master_id)
    snapshot = master['data']
    incoming_id = imported(changed_document(old, new), '新增单日稿.docx')
    candidate = next(r for r in rows('program') if r['data']['file_id'] == incoming_id)
    assert candidate['status'] == 'conflict'
    assert candidate['data']['conflict_with'] == master['id']
    assert any(new in b['original_text'] for b in candidate['data']['blocks'])
    assert get(master['id'])['data'] == snapshot


def test_ancillary_content_difference_is_not_silently_deduplicated():
    master_id = imported(document(comment='示例责编点评'), '母稿.docx', role='master')
    doc = Document(io.BytesIO(document(comment='示例责编点评')))
    doc.sections[0].footer.paragraphs[0].text = '本次补充核对说明'
    output = io.BytesIO()
    doc.save(output)
    incoming_id = imported(output.getvalue(), '新稿.docx')
    candidate = next(r for r in rows('program') if r['data']['file_id'] == incoming_id)
    assert candidate['status'] == 'conflict'
    assert get(candidate['data']['conflict_with'])['data']['file_id'] == master_id


def test_identical_text_in_different_docx_package_still_deduplicates():
    first_id = imported(document(comment='示例责编点评'), '母稿.docx', role='master')
    doc = Document(io.BytesIO(document(comment='示例责编点评')))
    doc.core_properties.subject = '不同文件属性，正文相同'
    output = io.BytesIO()
    doc.save(output)
    incoming_id = imported(output.getvalue(), '另存的新稿.docx')
    assert first_id != incoming_id
    assert len(rows('program')) == 1
    assert any(r['data']['file_id'] == incoming_id for r in rows('duplicate'))
