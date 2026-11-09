import pytest
from backend.app.documents import heading
@pytest.mark.parametrize('text',['主任意见','主任审片意见','审片意见','一、主任意见：','五、主任审片意见',' ３．主 任 审 片 意 见：','程主任意见','一、修改意见及程主任点评'])
def test_review_alias(text):assert heading(text)=='review_opinion'
@pytest.mark.parametrize('text',['主编点评','主编有话说','三、主编点评：','责编有话说','责编点评'])
def test_editor_alias(text):assert heading(text)=='editor_comment'
@pytest.mark.parametrize('text',['主任意见应该结合实际情况考虑，记者体会还需补充。','主编点评说这期节目很好，建议继续关注这一主题。','主任点评需要结合现场调查进一步完善。','程主任点评认为采访还需深入。','2026年9月1日《今日评说》审片意见'])
def test_body_not_heading(text):assert heading(text) is None

