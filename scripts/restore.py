import os,sys,zipfile,shutil,datetime
from pathlib import Path
root=Path(os.environ['REVIEW_HOME']).resolve()
backup=Path(sys.argv[1]).resolve()
with zipfile.ZipFile(backup) as z:
    for info in z.infolist():
        path=(root/info.filename).resolve()
        if not path.is_relative_to(root) or info.file_size>1024**3:raise ValueError('不安全的备份内容')
    if 'review.db' not in z.namelist():raise ValueError('备份缺少数据库')
    safety=root/'backups'/('before-restore-'+datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
    safety.mkdir(parents=True)
    for name in ('review.db','sources','exports','converted'):
        p=root/name
        if p.is_file():shutil.copy2(p,safety/name)
        elif p.is_dir():shutil.copytree(p,safety/name)
    z.extractall(root)
# Repair absolute data paths when restored onto a new work directory.
import sqlite3,json
with sqlite3.connect(root/'review.db') as db:
    for id,kind,data in db.execute("select id,kind,data from records where kind in ('file','export')").fetchall():
        d=json.loads(data)
        for key in ('path','audit'):
            if key in d:
                old=Path(d[key]); folder='sources' if kind=='file' else 'exports'
                parts=old.parts; idx=parts.index(folder);d[key]=str(root.joinpath(*parts[idx:]))
        db.execute('update records set data=? where id=?',(json.dumps(d,ensure_ascii=False),id))
print('恢复成功；API密钥需要在当前Windows账户中重新配置。')
