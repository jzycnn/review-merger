import json, asyncio, sqlite3, datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .core import *
from .documents import export_word,verify_export_format,validate,analyze_template
from .worker import ingest,scan
app=FastAPI(title='《今日评说》AI审片意见智能整理系统')
@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'):
        return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'禁止跨站请求'},status_code=403)
    if request.headers.get('host','').split(':')[0] not in ('127.0.0.1','localhost','testserver'):
        return __import__('starlette.responses',fromlist=['JSONResponse']).JSONResponse({'detail':'无效主机'},status_code=403)
    return await call_next(request)
@app.exception_handler(ValueError)
async def bad(request,exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail':str(exc)},status_code=400)
def checkmonth(month):
    import re
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month):raise ValueError('月份格式应为YYYY-MM')
@app.get('/api/state')
def state(month:str):
    checkmonth(month)
    result={k:rows(k,month) for k in ('file','program','job','duplicate','export','reset')}
    result['export'].sort(key=lambda r:r['data'].get('created',''),reverse=True)
    return result | {'months':sorted(set(r['month'] for r in rows('file')),reverse=True)}
@app.post('/api/reset')
def reset_month(body:dict):
    month=body.get('month','');checkmonth(month)
    if body.get('confirm_month')!=month:raise ValueError('请确认要清除的月份')
    from .reset import request_reset
    return request_reset(month,body.get('mode','restart'))
@app.post('/api/month')
def month(body:dict):
    checkmonth(body['month']);put('active_month',body);return {'ok':True}
@app.post('/api/upload')
async def upload(month:str=Form(...),role:str=Form('daily'),file:UploadFile=File(...)):
    checkmonth(month);content=await file.read(50*1024*1024+1)
    if len(content)>50*1024*1024:raise ValueError('单文件不能超过50MB')
    return {'id':ingest(content,file.filename,month,role)}
@app.post('/api/scan')
def scan_api(body:dict):
    checkmonth(body['month']);return {'count':scan(body['month'],body.get('role','daily'))}
@app.get('/api/events')
async def events(month:str):
    checkmonth(month)
    async def generate():
        while True:
            yield 'data: '+json.dumps(state(month),ensure_ascii=False)+'\n\n'
            await asyncio.sleep(2)
    return StreamingResponse(generate(),media_type='text/event-stream')
@app.post('/api/retry/{id}')
def retry(id:str):
    r=get(id)
    if r['kind']!='job' or r['status']!='failed':raise ValueError('只能重试失败任务')
    update(id,{k:v for k,v in r['data'].items() if k not in ('error','ai_error')},'queued');return {'ok':True}
@app.get('/api/history/{id}')
def history(id:str):return [r for r in rows('history') if r['status']==id]
@app.get('/api/source/{id}')
def source(id:str):
    r=get(id)
    if r['kind']!='file':raise ValueError('不是来源文件')
    return FileResponse(r['data']['path'],filename=r['data']['name'])
class ManualCommentUpdate(BaseModel):
    version: int = Field(ge=1)
    text: str = Field(max_length=100000)

class SuggestionRequest(BaseModel):
    version:int=Field(ge=1)
    refresh:bool=False

@app.post('/api/program/{id}/comment-suggestion')
def comment_suggestion(id:str,body:SuggestionRequest):
    from .comment_ai import suggest
    return suggest(id,body.version,body.refresh)

@app.get('/api/comment-reference')
def comment_reference():
    from .comment_ai import examples
    bank=examples()
    from .ai_client import cooldown_state
    pause=cooldown_state()
    return {'paused':pause,'count':len(bank),'sources':list(dict.fromkeys(e['source'] for e in bank)),'enabled':bool(config().get('enabled'))}

@app.put('/api/program/{id}/comment')
def save_comment(id:str,body:ManualCommentUpdate):
    r=get(id)
    if r['kind']!='program' or r['status']=='superseded':raise ValueError('该节目不能编辑')
    d=r['data'];d['editor_comment_manual']=body.text;d['confirmed']=False
    update(id,d,'conflict' if r['status']=='conflict' else 'pending',body.version)
    return get(id)

@app.put('/api/program/{id}')
def edit(id:str,body:dict):
    r=get(id)
    if r['kind']!='program':raise ValueError('不是节目记录')
    d=r['data'];p=Program.model_validate(body['program'])
    p.review_start=d['program'].get('review_start');p.review_end=d['program'].get('review_end')
    issues=validate(Recognition(programs=[p]),d['blocks'],'')
    if p.review_date and not p.review_date.startswith(r['month']):issues.append('月份不匹配')
    # Source IDs are immutable; editorial text lives in its own audited field.
    if 'editor_comment_manual' in body:
        comment=ManualCommentUpdate(version=body['version'],text=body['editor_comment_manual'])
        d['editor_comment_manual']=comment.text
    d['program']=p.model_dump();d['issues']=issues;d['confirmed']=body.get('confirmed',False)
    if body.get('acknowledge'):
        d['acknowledged_issues']=[i for i in issues if i in ('复合栏目责任主体需核对','正文与文件名日期冲突','DOC使用内置文本读取，请对照原件核实段落及表格')]
    issues=[i for i in issues if i not in d.get('acknowledged_issues',[])]
    d['issues']=issues
    if d['confirmed'] and issues:raise ValueError('请先处理：'+'；'.join(issues))
    status='verified' if d['confirmed'] else 'pending'
    if r['status']=='conflict':status='conflict'
    update(id,d,status,body['version']);return {'ok':True}
@app.post('/api/resolve/{id}')
def resolve(id:str,body:dict):
    r=get(id);d=r['data'];action=body['action']
    if r['status']!='conflict':raise ValueError('此记录没有待处理冲突')
    old=get(d['conflict_with'])
    if action=='keep':update(id,d,'superseded')
    elif action=='adopt':update(old['id'],old['data'],'superseded');update(id,d,'pending')
    elif action=='merge':
        od=old['data'];op=Program.model_validate(od['program']);np=Program.model_validate(d['program'])
        od['blocks']+=d['blocks'];op.sections+=np.sections;op.metadata_ids+=np.metadata_ids
        notes=[od.get('editor_comment_manual'),d.get('editor_comment_manual')]
        if any(note is not None for note in notes):od['editor_comment_manual']='\n'.join(note for note in notes if note)
        od['program']=op.model_dump();od['issues']=['手动合并后请核对所有段落归属'];od['confirmed']=False
        update(old['id'],od,'pending');update(id,d,'superseded')
    else:raise ValueError('无效操作')
    put('resolution',{'candidate':id,'original':old['id'],'action':action},r['month']);return {'ok':True}
@app.post('/api/split/{id}')
def split(id:str,body:dict):
    r=get(id);d=r['data'];parts=[Program.model_validate(p) for p in body['programs']]
    issues=validate(Recognition(programs=parts),d['blocks'],'')
    if any('覆盖' in i or '重复' in i for i in issues):raise ValueError('拆分必须完整且唯一分配原文块')
    for p in parts:
        ids=set(p.metadata_ids)
        for s in p.sections:
            ids.update(s.source_block_ids)
            if s.heading_id:ids.add(s.heading_id)
        put('program',dict(d,program=p.model_dump(),blocks=[b for b in d['blocks'] if b['source_block_id'] in ids],issues=issues,confirmed=False),r['month'],'pending')
    update(id,d,'superseded');return {'ok':True}
@app.get('/api/settings')
def settings():return config() | {'home':str(ROOT)}
@app.post('/api/settings')
def settings_save(body:dict):
    import keyring
    from urllib.parse import urlparse
    if urlparse(body['base_url']).scheme not in ('https','http'):raise ValueError('API地址无效')
    if body.get('api_key'):keyring.set_password('review-merger','api-key',body.pop('api_key'))
    body.pop('api_key',None)
    from .ai_client import resolve_proxy
    resolve_proxy(body)
    timeout=int(body.get('read_timeout_s',120))
    if not 20<=timeout<=300:raise ValueError('响应超时应为20至300秒')
    put('settings',{k:body[k] for k in ('enabled','model','base_url')}|{'proxy_url':body.get('proxy_url','').strip(),'read_timeout_s':timeout});return {'ok':True}
@app.post('/api/settings/test')
def test_ai_connection():
    from .ai_client import create_client,error_message,clear_cooldown
    try:
        with create_client(ignore_cooldown=True) as client:
            result=client.chat.completions.create(model=config()['model'],messages=[{'role':'user','content':'只回复OK。这是网络与模型连接测试。'}],max_tokens=64)
        clear_cooldown()
        return {'ok':True,'model':config()['model'],'message':'接口与模型连接成功，已解除此前额度暂停（未发送审片文档）'}
    except ValueError:raise
    except Exception as exc:raise ValueError(error_message(exc)) from None

@app.post('/api/export')
def export(body:dict):
    month=body['month'];checkmonth(month);draft=bool(body.get('draft'));rr=rows('program',month)
    selected=[r for r in rr if r['status'] not in ('superseded','conflict')]
    errors=[]
    if not selected:raise ValueError('没有可导出的节目')
    for f in rows('file',month):
        if f['status']!='success':errors.append('存在未成功处理的文件')
    if any(r['status']=='conflict' for r in rr):errors.append('存在未解决版本冲突')
    for r in selected:
        d=r['data'];local_issues=validate(Recognition(programs=[Program.model_validate(d['program'])]),d['blocks'],'')
        errors += [e for e in local_issues if e not in d.get('acknowledged_issues',[])]
        errors+=d.get('issues',[])
        if d['program'].get('review_date') and not d['program']['review_date'].startswith(month):errors.append('节目日期不在当前月份')
        if not d.get('confirmed'):errors.append('存在未经人工核实的节目')
        original_comments=[b['original_text'] for section in d['program']['sections'] if section['type']=='editor_comment' for block_id in section['source_block_ids'] for b in d['blocks'] if b['source_block_id']==block_id]
        if not d.get('editor_comment_manual','').strip() and not any(text.strip() for text in original_comments):
            errors.append((d['program'].get('review_date') or '日期未填写')+'：责编有话说尚未填写')
    if errors and not draft:raise ValueError('正式导出被阻止：'+'；'.join(set(errors)))
    tid=uid(); y,m=month.split('-');name=f'《今日评说》{y}年{int(m)}月审片意见汇总'+('（待核对）' if draft else '')+'.docx'
    folder=ROOT/'exports'/tid;folder.mkdir();path=folder/name
    export_word(selected,month,path,Template(size=12,line_spacing=1.0),draft)
    checked_format=verify_export_format(path)
    created=datetime.datetime.now()
    download_name=Path(name).stem+'（小四单倍行距版_'+created.strftime('%Y%m%d_%H%M%S')+'）.docx'
    from openpyxl import Workbook
    wb=Workbook();ws=wb.active;ws.title='来源核对';ws.append(['节目','日期','来源文件','来源块','位置','原文栏目','原文','最终分类','状态','人工版本'])
    for r in selected:
        d=r['data'];p=d['program'];mapping={i:s['type'] for s in p['sections'] for i in s['source_block_ids']}
        for b in d['blocks']:
            vals=[p['program_title'],p['review_date'],d['file_id'],b['source_block_id'],b['location'],b['original_section_title'],b['original_text'],mapping.get(b['source_block_id'],'元信息或栏目标题'),r['status'],r['version']]
            ws.append(vals)
            for cell in ws[ws.max_row]:
                if isinstance(cell.value,str):cell.data_type='s'
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    hist=wb.create_sheet('人工修订历史');hist.append(['节目ID','历史版本ID','历史结构及原文'])
    selected_ids={r['id'] for r in selected}
    for h in rows('history',month):
        if h['status'] in selected_ids:
            hist.append([h['status'],h['id'],json.dumps(h['data'],ensure_ascii=False)])
            for cell in hist[hist.max_row]:cell.data_type='s'
    manual=wb.create_sheet('手工填写点评');manual.append(['节目ID','日期','节目名称','责编有话说（手填）','版本'])
    for r in selected:
        if r['data'].get('editor_comment_manual') is not None:
            manual.append([r['id'],r['data']['program']['review_date'],r['data']['program']['program_title'],r['data']['editor_comment_manual'],r['version']])
            for cell in manual[manual.max_row]:
                if isinstance(cell.value,str):cell.data_type='s'
    wb.save(folder/'核对表.xlsx')
    put('export',{'path':str(path),'audit':str(folder/'核对表.xlsx'),'name':name,'download_name':download_name,'format':checked_format,'draft':draft,'issues':list(set(errors)),'created':created.isoformat()},month,'draft' if draft else 'complete',tid)
    return {'word':f'/api/download/{tid}/word','audit':f'/api/download/{tid}/audit'}
@app.get('/api/download/{id}/{kind}')
def download(id:str,kind:str):
    r=get(id)
    if r['kind']!='export' or kind not in ('word','audit'):raise ValueError('无效导出记录')
    return FileResponse(r['data']['path' if kind=='word' else 'audit'],filename=r['data'].get('download_name',r['data']['name']) if kind=='word' else '核对表.xlsx',headers={'Cache-Control':'no-store'})
@app.post('/api/backup')
def backup():
    import zipfile
    name=uid()+'.zip';path=ROOT/'backups'/name
    snapshot=ROOT/'backups'/(name+'.db')
    with sqlite3.connect(ROOT/'review.db') as src,sqlite3.connect(snapshot) as dst:src.backup(dst)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(snapshot,'review.db')
        for folder in ('sources','exports','converted'):
            for p in (ROOT/folder).rglob('*'):
                if p.is_file():z.write(p,str(p.relative_to(ROOT)))
    snapshot.unlink();put('backup',{'path':str(path)});return {'path':str(path)}
static=Path(__file__).resolve().parents[2]/'frontend'/'dist'
if static.exists():app.mount('/',StaticFiles(directory=static,html=True),name='web')
