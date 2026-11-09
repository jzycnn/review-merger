"""Shared transport for AI parsing and comment generation."""
import urllib.request
from urllib.parse import urlsplit
import httpx
from .core import config,rows,put,update

def resolve_proxy(settings):
    explicit=settings.get('proxy_url','').strip()
    if explicit:
        parsed=urlsplit(explicit)
        if parsed.scheme not in ('http','https') or not parsed.hostname:raise ValueError('代理地址格式无效，请填写http://主机:端口')
        return explicit
    # Resolve afresh so a desktop proxy change is visible without re-login.
    proxies=urllib.request.getproxies()
    endpoint=urlsplit(settings['base_url'])
    if endpoint.hostname and urllib.request.proxy_bypass(endpoint.hostname):return None
    return proxies.get(endpoint.scheme) or proxies.get('all')

def cooldown_state():
    import time
    current=config()
    matches=[r['data'] for r in rows('ai_cooldown') if r['data'].get('model')==current.get('model') and r['data'].get('base_url')==current.get('base_url') and r['data'].get('until',0)>time.time()]
    return max(matches,key=lambda d:d['until']) if matches else None

def clear_cooldown():
    import time
    current=config()
    for r in rows('ai_cooldown'):
        d=r['data']
        if d.get('model')==current.get('model') and d.get('base_url')==current.get('base_url') and d.get('until',0)>time.time():
            update(r['id'],dict(d,until=0,reason='连接测试成功，已解除此前额度暂停'),'cleared')

def create_client(ignore_cooldown=False):
    import keyring
    from openai import OpenAI
    settings=config()
    if not settings.get('enabled'):raise ValueError('外部AI尚未启用')
    pause=cooldown_state()
    if pause and not ignore_cooldown:raise ValueError(pause['reason'])
    key=keyring.get_password('review-merger','api-key')
    if not key:raise ValueError('尚未配置API Key，请先到设置中配置模型')
    timeout=httpx.Timeout(float(settings.get('read_timeout_s',120)),connect=10,write=30,pool=10)
    transport=httpx.Client(proxy=resolve_proxy(settings),trust_env=False,timeout=timeout)
    return OpenAI(api_key=key,base_url=settings['base_url'],http_client=transport,timeout=timeout,max_retries=0)

def error_message(exc):
    from openai import APITimeoutError,APIConnectionError,AuthenticationError,RateLimitError,NotFoundError,BadRequestError,PermissionDeniedError,InternalServerError
    if isinstance(exc,APITimeoutError):return 'Gemini/模型响应超时。请检查设置中的代理地址、本机代理是否运行，或稍后重试；已填写内容不受影响'
    if isinstance(exc,APIConnectionError):return '无法连接模型接口。请检查代理、网络和API地址；已填写内容不受影响'
    if isinstance(exc,AuthenticationError):return 'API密钥验证失败，请在设置中重新保存有效密钥'
    if isinstance(exc,RateLimitError):
        import re,time,json
        body=getattr(exc,'body',{})
        detail=json.dumps(body,ensure_ascii=False)
        daily='per day' in detail.lower() or 'RequestsPerDay' in detail
        delay=re.search(r'"retryDelay"\s*:\s*"(\d+)s"',detail)
        seconds=int(delay.group(1)) if delay else (3600 if daily else 60)
        limit=re.search(r'"quotaValue"\s*:\s*"(\d+)"',detail)
        reason=('当前模型今日免费请求额度已用完'+('（每天'+limit.group(1)+'次）' if limit else '') if daily else '当前模型请求频率或额度受限')+'，已暂停自动生成，请等待额度恢复；手工内容保留'
        current=config();put('ai_cooldown',{'model':current.get('model'),'base_url':current.get('base_url'),'until':time.time()+seconds,'reason':reason})
        return reason
    if isinstance(exc,InternalServerError):return '模型服务暂时出错，请稍后重试；已填写内容保留'
    if isinstance(exc,NotFoundError):return '模型或API路径不存在，请检查模型名称和API地址'
    if isinstance(exc,PermissionDeniedError):return '模型服务拒绝访问，请检查项目权限、密钥权限及地区可用性'
    if isinstance(exc,BadRequestError):return '模型拒绝请求参数，请检查该模型是否支持结构化输出'
    return 'AI参考生成失败（'+type(exc).__name__+'），请检查设置后重试；已填写内容保留'
