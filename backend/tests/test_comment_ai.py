import pytest
from backend.tests.test_workflow import imported,document
from backend.app.core import rows,put,get,update
from backend.app.main import app
from backend.app import comment_ai
from fastapi.testclient import TestClient
client=TestClient(app)
def setup_record():
 f=imported(document(),'20260901.docx')
 return next(r for r in rows('program') if r['data']['file_id']==f)
def enable():put('settings',{'enabled':True,'model':'mock-model','base_url':'https://example.invalid/v1'})
def test_disabled_ai_never_calls_model(monkeypatch):
 r=setup_record();monkeypatch.setattr(comment_ai,'call_model',lambda m:pytest.fail('不应发送外部请求'))
 response=client.post('/api/program/'+r['id']+'/comment-suggestion',json={'version':r['version']})
 assert response.status_code==400 and '尚未启用' in response.json()['detail']
def test_reference_generation_cached_and_does_not_save_manual(monkeypatch):
 r=setup_record();enable();calls=[]
 bid=r['data']['blocks'][3]['source_block_id']
 def fake(messages):
  calls.append(messages)
  assert '历史措辞参考' in messages[1]['content'] and '当期材料' in messages[1]['content']
  return comment_ai.CommentSuggestion(text='参考点评，建议补充现场观察。',evidence_block_ids=[bid],insufficient_context=False)
 monkeypatch.setattr(comment_ai,'call_model',fake)
 url='/api/program/'+r['id']+'/comment-suggestion';body={'version':r['version']}
 a=client.post(url,json=body);b=client.post(url,json=body)
 assert a.status_code==200,a.text
 assert b.json()['cached'] and len(calls)==1
 assert get(r['id'])==r and 'editor_comment_manual' not in get(r['id'])['data']
 assert len(rows('suggestion'))==1
 assert set(a.json()['references']).issubset({'虚构示例（非真实审片资料）'})
def test_bad_evidence_rejected(monkeypatch):
 r=setup_record();enable()
 monkeypatch.setattr(comment_ai,'call_model',lambda m:comment_ai.CommentSuggestion(text='错误参考',evidence_block_ids=['不存在'],insufficient_context=False))
 response=client.post('/api/program/'+r['id']+'/comment-suggestion',json={'version':r['version']})
 assert response.status_code==400 and not rows('suggestion')
def test_generation_error_keeps_saved_text(monkeypatch):
 r=setup_record();d=r['data'];d['editor_comment_manual']='已写好的点评';update(r['id'],d);r=get(r['id']);enable()
 def fail(m):raise ValueError('模拟网络中断')
 monkeypatch.setattr(comment_ai,'call_model',fail)
 result=client.post('/api/program/'+r['id']+'/comment-suggestion',json={'version':r['version']})
 assert result.status_code==400 and get(r['id'])['data']['editor_comment_manual']=='已写好的点评'
def test_context_changed_during_generation_rejected(monkeypatch):
 r=setup_record();enable()
 def fake(m):
  update(r['id'],dict(r['data'],editor_comment_manual='并发人工修订'))
  return comment_ai.CommentSuggestion(text='迟到的AI结果',evidence_block_ids=[r['data']['blocks'][3]['source_block_id']],insufficient_context=False)
 monkeypatch.setattr(comment_ai,'call_model',fake)
 result=client.post('/api/program/'+r['id']+'/comment-suggestion',json={'version':r['version']})
 assert result.status_code==400 and '生成期间节目已修改' in result.json()['detail']
 assert not rows('suggestion')
def test_insufficient_context_does_not_invent(monkeypatch):
 r=setup_record();enable()
 monkeypatch.setattr(comment_ai,'call_model',lambda m:comment_ai.CommentSuggestion(text='',evidence_block_ids=[],insufficient_context=True))
 result=client.post('/api/program/'+r['id']+'/comment-suggestion',json={'version':r['version']})
 assert result.status_code==200 and result.json()['text']==''
def test_reference_bank_contains_only_fictional_example():
 bank=comment_ai.examples();assert len(bank)==1
 assert {e['source'] for e in bank}=={'虚构示例（非真实审片资料）'}
