import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.documents import read,analyze_template,parse,validate
root=Path(__file__).resolve().parents[1]
names=['《今日评说》9月审片意见.docx','20260929《今日评说》审片意见.doc','2026年9月1日《今日评说》审片意见：《街头演艺新政》.docx']
report=[]
for i,name in enumerate(names):
    path=root/'samples'/name
    if not path.exists():report.append({'name':name,'status':'missing'});continue
    try:
        b=read(path,str(i));rec=parse(b,name)
    except Exception as e:
        report.append({'name':name,'status':'failed','error':str(e)});continue
    report.append({'name':name,'blocks':b,'recognition':rec.model_dump(),'issues':validate(rec,b,name),'styles':analyze_template(path)})
(root/'docs'/'sample-analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'name':r['name'],'status':r.get('status','analyzed')} for r in report],ensure_ascii=False))
