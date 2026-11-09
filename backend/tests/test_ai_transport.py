import httpx,time
from openai import RateLimitError,APITimeoutError,AuthenticationError
from backend.app.ai_client import error_message,cooldown_state,resolve_proxy
from backend.app.core import put

def test_explicit_proxy_preferred():
 assert resolve_proxy({'proxy_url':'http://127.0.0.1:10808','base_url':'https://example.invalid'})=='http://127.0.0.1:10808'
def test_invalid_proxy_rejected():
 import pytest
 with pytest.raises(ValueError):resolve_proxy({'proxy_url':'file:///bad','base_url':'https://example.invalid'})
def test_daily_quota_pause_and_different_model_not_blocked():
 put('settings',{'enabled':True,'model':'test-flash','base_url':'https://example.invalid'})
 response=httpx.Response(429,request=httpx.Request('POST','https://example.invalid'))
 exc=RateLimitError('quota',response=response,body=[{'error':{'message':'Generate content requests per day limit exceeded','details':[{'quotaValue':'20'},{'retryDelay':'9000s'}]}}])
 message=error_message(exc)
 assert '每天20次' in message and '今日' in message
 assert cooldown_state()['until']>time.time()+8900
 put('settings',{'enabled':True,'model':'another-model','base_url':'https://example.invalid'})
 assert cooldown_state() is None
def test_timeout_and_bad_key_messages_are_distinct():
 timeout=APITimeoutError(request=httpx.Request('POST','https://example.invalid'))
 assert '超时' in error_message(timeout)
 response=httpx.Response(401,request=httpx.Request('POST','https://example.invalid'))
 assert '密钥验证失败' in error_message(AuthenticationError('invalid',response=response,body={}))

def test_connection_recheck_can_clear_old_pause(monkeypatch):
 from backend.app import ai_client
 from backend.app.core import rows
 from backend.app.main import app
 from fastapi.testclient import TestClient
 import types
 put('settings',{'enabled':True,'model':'test-flash','base_url':'https://example.invalid'})
 put('ai_cooldown',{'model':'test-flash','base_url':'https://example.invalid','until':time.time()+5000,'reason':'旧免费额度已满'})
 assert ai_client.cooldown_state()
 flags=[]
 class FakeClient:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs:object()))
 def client(ignore_cooldown=False):flags.append(ignore_cooldown);return FakeClient()
 monkeypatch.setattr(ai_client,'create_client',client)
 response=TestClient(app).post('/api/settings/test',json={})
 assert response.status_code==200 and flags==[True]
 assert ai_client.cooldown_state() is None
 assert rows('ai_cooldown')[0]['status']=='cleared'

def test_failed_recheck_preserves_pause(monkeypatch):
 from backend.app import ai_client
 from backend.app.main import app
 from fastapi.testclient import TestClient
 put('settings',{'enabled':True,'model':'test-flash','base_url':'https://example.invalid'})
 put('ai_cooldown',{'model':'test-flash','base_url':'https://example.invalid','until':time.time()+5000,'reason':'旧免费额度已满'})
 def failed(**kwargs):raise ValueError('网络仍不可用')
 monkeypatch.setattr(ai_client,'create_client',failed)
 response=TestClient(app).post('/api/settings/test',json={})
 assert response.status_code==400 and ai_client.cooldown_state()
