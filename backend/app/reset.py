"""Month reset commands run serially in the independent worker."""
import json,zipfile,datetime
from .core import ROOT,Session,Row,uid,pack

def request_reset(month,mode):
    if mode not in ('restart','clear'):raise ValueError('无效清除方式')
    with Session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        prior=db.query(Row).filter_by(kind='reset',month=month,status='queued').first()
        if prior:return {'id':prior.id,'status':'queued'}
        if not db.query(Row).filter_by(kind='file',month=month).count():raise ValueError('本月没有已导入文件')
        command=Row(id=uid(),kind='reset',month=month,status='queued',data=json.dumps({'mode':mode}))
        db.add(command);db.commit();return {'id':command.id,'status':'queued'}

def execute_reset(command_id):
    # Backup and database changes are all-or-nothing; failure leaves originals intact.
    with Session() as db:
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
        command=db.get(Row,command_id)
        if not command or command.status!='queued':return
        mode=json.loads(command.data)['mode'];month=command.month
        snapshot=db.query(Row).filter_by(month=month).all()
        files=[r for r in snapshot if r.kind=='file']
        final=ROOT/'backups'/('reset-'+month+'-'+uid()+'.zip');temp=final.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('month-records.json',json.dumps([pack(r) for r in snapshot],ensure_ascii=False,indent=2))
                for r in files:
                    from pathlib import Path
                    path=Path(json.loads(r.data)['path'])
                    if not path.is_file():raise ValueError('来源文件缺失，已取消清除：'+path.name)
                    archive.write(path,'sources/'+path.name)
            temp.replace(final)
            kinds=['program','job','duplicate','history','resolution','suggestion']
            if mode=='clear':kinds.append('file')
            db.query(Row).filter(Row.month==month,Row.kind.in_(kinds)).delete(synchronize_session=False)
            if mode=='restart':
                for r in files:
                    raw=json.loads(r.data)
                    # Keep identity, original content path, role and hash. Remove derived fields only.
                    raw={k:v for k,v in raw.items() if k in ('name','path','size','sha256','role')}
                    r.data=json.dumps(raw,ensure_ascii=False);r.status='queued';r.version+=1
                    db.add(Row(id=uid(),kind='job',month=month,status='queued',data=json.dumps({'file_id':r.id,'step':'文件检查'})))
            else:
                # Suspend folder monitoring until the user explicitly starts another import.
                for active in db.query(Row).filter_by(kind='active_month').all():
                    if json.loads(active.data).get('month')==month:db.delete(active)
            command.status='done';command.data=json.dumps({'mode':mode,'backup':str(final),'file_count':len(files),'completed':datetime.datetime.now().isoformat()},ensure_ascii=False)
            db.commit()
        except Exception:
            if temp.exists():temp.unlink()
            db.rollback();raise

def pending_resets():
    from .core import rows,update
    pending=[r for r in rows('reset') if r['status']=='queued']
    for r in pending:
        try:execute_reset(r['id'])
        except Exception as exc:
            update(r['id'],dict(r['data'],error=str(exc)),'failed')
    return bool(pending)
