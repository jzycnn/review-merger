import re, hashlib
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, Cm
from .core import Block, Program, Section, Recognition, ROOT, Template

def convert(path):
    if path.suffix.lower()=='.docx': return path
    word=None;initialized=False
    try:
        import pythoncom, win32com.client
        pythoncom.CoInitialize();initialized=True
        word=win32com.client.DispatchEx('Word.Application')
        word.Visible=False;word.DisplayAlerts=0;word.AutomationSecurity=3
        doc=word.Documents.Open(str(path.resolve()),ReadOnly=True,AddToRecentFiles=False)
        try:
            out=ROOT/'converted'/(path.stem+'.docx')
            doc.SaveAs2(str(out),FileFormat=16)
            Document(out)
            return out
        finally:doc.Close(False)
    except Exception as exc:
        raise RuntimeError('Microsoft Word转换接口不可用：'+type(exc).__name__) from exc
    finally:
        try:
            if word is not None:word.Quit()
        except Exception:pass
        finally:
            if initialized:pythoncom.CoUninitialize()

def read(path,source):
    path=Path(path)
    try:converted=convert(path)
    except RuntimeError:
        if path.suffix.lower()!='.doc':raise
        from .doc_binary import read_blocks
        try:return read_blocks(path,source)
        except Exception as exc:
            raise RuntimeError('Word转换不可用；内置DOC读取失败：'+str(exc)) from exc
    doc=Document(converted); blocks=[]; pi=0;ti=0
    unsupported=('w:txbxContent','w:ins','w:del','w:drawing','w:object')
    if any(list(doc.element.iter(qn(tag))) for tag in unsupported):
        raise ValueError('存在文本框、修订或图片对象，请另存普通段落版本后导入，避免遗漏')
    if any(len(list(t.iter(qn('w:tbl'))))>1 for t in doc.element.body.iter(qn('w:tbl'))):
        raise ValueError('存在嵌套表格，请转换为普通段落')
    def add(text,location,p=None,t=None):
        if text.strip():blocks.append(Block(source_file_id=source,source_block_id=f'{source}:{len(blocks)}',paragraph_index=p,table_index=t,original_text=text,location=location).model_dump())
    from docx.text.paragraph import Paragraph
    from docx.table import Table
    for element in doc.element.body:
        if element.tag==qn('w:p'):
            add(Paragraph(element,doc).text,'body',pi);pi+=1
        elif element.tag==qn('w:tbl'):
            table=Table(element,doc); seen=set()
            for row in table.rows:
                for cell in row.cells:
                    if cell._tc in seen:continue
                    seen.add(cell._tc)
                    for p in cell.paragraphs:add(p.text,'table',None,ti)
            ti+=1
    for si,sec in enumerate(doc.sections):
        for name in ('header','footer'):
            for p in getattr(sec,name).paragraphs:add(p.text,f'{name}:{si}')
    return blocks
DATE=re.compile(r'(20\d{2})[年./\-](\d{1,2})[月./\-](\d{1,2})日?|(20\d{2})(\d{2})(\d{2})')
def dates(text):
    import datetime
    out=[]
    for m in DATE.finditer(text):
        a=m.groups(); v=a[:3] if a[0] else a[3:]
        try:out.append(datetime.date(*map(int,v)).isoformat())
        except ValueError:pass
    return list(dict.fromkeys(out))
def section_label(text):
    """Reject栏目 labels as automatic titles, including quoted or numbered labels."""
    s=re.sub(r'^[\s（(]*[一二三四五六七八九十百0-9０-９]+[、.．）)\s]+','',text.strip())
    s=re.sub(r'[\s：:、，,。；;（）()《》【】\[\]]','',s)
    return bool(re.fullmatch(r'(?:(?:领导|主任|主编|责编|责任编辑|编辑|记者|程主任))?(?:审片意见|审看意见|修改意见|意见|点评|有话说|体会|心得)|(?:节目名称|节目标题|标题|审片时间|审片人员)',s)) or heading(text) is not None

def heading(text):
    # Recognize heading aliases, never classify a whole opinion paragraph by keywords.
    s=re.sub(r'^[一二三四五六七八九十百0-9０-９]+[、.．）)\s]+','',text.strip())
    s=re.sub(r'[\s：:、，,。；;（）()]','',s)
    if not s or len(s)>36 or dates(s) or '今日评说' in s:return None
    if s in ('记者体会','记者心得','记者感想','记者采编体会'):return 'reporter_reflection'
    if re.fullmatch(r'(?:主编|责编|责任编辑|编辑)(?:点评|有话说|意见|审片意见)',s):return 'editor_comment'
    if s in ('修改意见','审看意见','审片意见','主任意见','主任审片意见','主任修改意见','主任审看意见','领导意见','领导审片意见','领导修改意见','领导审看意见','领导点评'):return 'review_opinion'
    # Preserve compound headings as one section, with the original responsibility labels.
    if re.fullmatch(r'(?:修改意见|审看意见|审片意见)(?:及|和|与).{0,8}主任(?:点评|意见|审片意见)',s):return 'review_opinion'
    if re.fullmatch(r'.{0,4}主任(?:意见|审片意见|修改意见|审看意见)',s):return 'review_opinion'
    return None

def parse(blocks,filename):
    ancillary=[b for b in blocks if b['location'].startswith(('header','footer'))]
    blocks=[b for b in blocks if not b['location'].startswith(('header','footer'))]
    programs=[]; p=None; current=None; lastdate=None
    preamble=[]
    for b in blocks:
        if not programs and p is None and not dates(b['original_text']) and not heading(b['original_text']) and '月审片意见' in b['original_text']:
            preamble.append(b['source_block_id']);continue
        text=b['original_text'];bid=b['source_block_id']; ds=dates(text)
        is_date=bool(ds and ('审片' in text or len(text)<32))
        if is_date:
            if p and (p.sections or p.program_title):programs.append(p);p=None
            lastdate=ds[0]
        if p is None:
            p=Program(review_date=lastdate,metadata_ids=preamble);preamble=[]
        titles=[t for t in re.findall('《([^》]+)》',text) if t!='今日评说' and not section_label(t)]
        if titles and p.program_title and titles[-1]!=p.program_title:
            programs.append(p);p=Program(review_date=lastdate);current=None
        if titles:p.program_title=titles[-1]
        typ=heading(text)
        bare_title=not typ and not section_label(text) and not titles and not is_date and not p.program_title and p.review_date and not p.sections and not re.search('审片.*时间|结束时间|审片人员',text) and len(text.strip())<=90
        if bare_title:p.program_title=text.strip()
        if typ:
            current=Section(type=typ,original_heading=text,heading_id=bid);p.sections.append(current);b['original_section_title']=text
        elif is_date or titles or bare_title or re.search('审片.*时间|结束时间|审片人员',text):
            p.metadata_ids.append(bid)
            if '人员' in text:p.reviewers_raw=text
            times=re.findall(r'\d{1,2}[:：]\d{2}',text)
            if times:p.review_start=times[0];p.review_end=times[1] if len(times)>1 else None
        else:
            if current is None:current=Section(type='unclassified');p.sections.append(current)
            current.source_block_ids.append(bid);b['original_section_title']=current.original_heading
        if is_date:current=None
    if p:programs.append(p)
    auxiliary_dates=list(dict.fromkeys(d for b in ancillary for d in dates(b['original_text'])))
    if programs:programs[0].metadata_ids += [b['source_block_id'] for b in ancillary]
    fallback=auxiliary_dates if len(auxiliary_dates)==1 else dates(filename)
    for p in programs:
        if not p.review_date and len(fallback)==1:p.review_date=fallback[0]
    return Recognition(programs=programs)

def validate(rec,blocks,filename):
    ids={b['source_block_id'] for b in blocks};used=[];issues=[]
    if any(b['location']=='doc_binary' for b in blocks):
        from .doc_binary import WARNING
        issues.append(WARNING)
    filedates=dates(filename)
    for p in rec.programs:
        if not p.review_date:issues.append('缺少日期')
        elif not re.fullmatch(r'\d{4}-\d{2}-\d{2}',p.review_date):issues.append('日期格式错误')
        else:
            import datetime
            try:datetime.date.fromisoformat(p.review_date)
            except ValueError:issues.append('日期无效')
        if filedates and p.review_date not in filedates:issues.append('正文与文件名日期冲突')
        if not p.program_title:issues.append('缺少节目名称')
        if not p.reviewers_raw:issues.append('缺少审片人员')
        used+=p.metadata_ids
        for s in p.sections:
            used+=s.source_block_ids
            if s.heading_id:used.append(s.heading_id)
            if s.type=='unclassified':issues.append('存在未归类原文')
            if '主任点评' in s.original_heading:issues.append('复合栏目责任主体需核对')
    if set(used)-ids:raise ValueError('识别返回不存在的来源ID')
    if len(used)!=len(set(used)):issues.append('来源块重复归属')
    if ids-set(used):issues.append('原始正文覆盖不完整')
    return list(dict.fromkeys(issues))

def export_word(records,month,path,template,draft=False):
    from collections import Counter
    # Fixed house style; old template settings can no longer alter exports.
    template=Template(size=12,line_spacing=1.0)
    doc=Document(); sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7)
    sec.top_margin=sec.bottom_margin=Cm(template.margin_cm)
    sec.left_margin=sec.right_margin=Cm(template.horizontal_margin_cm)
    for name in ('Normal','Title','Heading 1','Heading 2','Heading 3'):
        s=doc.styles[name];s.font.name='Times New Roman';s.font.size=Pt(template.size);s.font.color.rgb=__import__('docx').shared.RGBColor(0,0,0)
        s.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
        s.paragraph_format.line_spacing=template.line_spacing
        if name!='Normal':s.font.bold=True;s.paragraph_format.keep_with_next=True
    doc.styles['Normal'].paragraph_format.first_line_indent=Pt(template.first_indent_pt)
    y,m=month.split('-');doc.add_paragraph(f'《今日评说》{y}年{int(m)}月审片意见汇总'+('（待核对草稿）' if draft else ''),'Title')
    expected=[]
    last_date=None
    for record_index,r in enumerate(sorted(records,key=lambda r:((r['data']['program'].get('review_date') or '9999'),r['data']['program'].get('review_start') or '',r['data']['program'].get('program_title') or ''))):
        d=r['data'];p=Program.model_validate(d['program']);bm={b['source_block_id']:b['original_text'] for b in d['blocks']};emitted=set()
        if record_index and p.review_date!=last_date:
            from docx.oxml import OxmlElement
            previous=doc.paragraphs[-1]
            borders=OxmlElement('w:pBdr');line=OxmlElement('w:bottom')
            for key,value in {'val':'single','sz':'6','space':'8','color':'808080'}.items():line.set(qn('w:'+key),value)
            borders.append(line);previous._p.get_or_add_pPr().append(borders)
            previous.paragraph_format.space_after=Pt(12)
        last_date=p.review_date
        def emit(bid):
            if bid not in emitted:
                text=bm[bid]
                doc.add_paragraph(text);expected.append(text);emitted.add(bid)
        display_date='日期待核对'
        if p.review_date:
            yy,mm,dd=p.review_date.split('-');display_date=f'{yy}年{int(mm)}月{int(dd)}日'
        date_heading=display_date+'《今日评说》审片意见'
        doc.add_paragraph(date_heading,'Heading 1')
        if p.program_title:doc.add_paragraph('《'+p.program_title+'》','Heading 2')
        # Metadata source blocks remain verbatim, including combined title/date/time paragraphs.
        labels=[('review_opinion',template.review_label),('reporter_reflection','记者体会'),('editor_comment','责编有话说')]
        for i,(typ,label) in enumerate(labels):
            ss=[s for s in p.sections if s.type==typ]
            if ss or template.show_missing or typ=='editor_comment':doc.add_paragraph('一二三'[i]+'、'+label,'Heading 3')
            for s in ss:
                for bid in s.source_block_ids:emit(bid)
            if typ=='editor_comment' and d.get('editor_comment_manual'):
                for paragraph in d['editor_comment_manual'].split('\n'):
                    if paragraph.strip():doc.add_paragraph(paragraph);expected.append(paragraph)
        for s in p.sections:
            if s.type=='unclassified':
                doc.add_paragraph('待核对原文','Heading 3')
                for bid in s.source_block_ids:emit(bid)
        for bid in p.metadata_ids:
            raw=bm[bid].strip()
            generated=(date_heading,'《'+(p.program_title or '')+'》',p.program_title)
            date_label=bool(re.fullmatch(r'20\d{2}年\d{1,2}月\d{1,2}日《今日评说》审片意见',raw))
            if date_label or raw in generated or re.fullmatch(r'《今日评说》\d+月审片意见',raw):emitted.add(bid)
            else:emit(bid)
        assigned=emitted|{s.heading_id for s in p.sections}
        for bid in bm.keys()-assigned:emit(bid)
    for paragraph in doc.paragraphs:
        paragraph.paragraph_format.line_spacing=1.0
        for run in paragraph.runs:
            run.font.name='Times New Roman'
            run.font.size=Pt(12)
            fonts=run._element.get_or_add_rPr().get_or_add_rFonts()
            fonts.set(qn('w:eastAsia'),'宋体')
            for name in ('asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme'):
                fonts.attrib.pop(qn('w:'+name),None)
    doc.save(path)
    normalize_export_package(path)
    actual=Counter(p.text for p in Document(path).paragraphs)
    if any(actual[t]<n for t,n in Counter(expected).items()):raise ValueError('导出回读原文校验失败')
    return path

def verify_export_format(path):
    """Check the saved artifact, rather than trusting exporter settings."""
    import zipfile
    doc=Document(path)
    for paragraph in doc.paragraphs:
        if paragraph.paragraph_format.line_spacing!=1.0:
            raise ValueError('Word格式检查失败：行距不是1倍')
        for run in paragraph.runs:
            fonts=run._element.get_or_add_rPr().get_or_add_rFonts()
            if run.font.size is None or run.font.size.pt!=12 or any(fonts.get(qn('w:'+key))!=value for key,value in {'eastAsia':'宋体','ascii':'Times New Roman','hAnsi':'Times New Roman'}.items()):
                raise ValueError('Word格式检查失败：字号或字体不符合固定排版')
    with zipfile.ZipFile(path) as package:
        if any(b'MS Gothic' in package.read(name) for name in package.namelist() if name.startswith('word/') and name.endswith('.xml')):
            raise ValueError('Word格式检查失败：仍有MS Gothic字体')
    return {'version':'fixed-12pt-single-v1','label':'小四12磅 · 1倍行距 · 中文宋体 · 西文Times New Roman'}


def normalize_export_package(path):
    """Remove inherited Japanese/theme font definitions as well as run-level overrides."""
    import zipfile
    from lxml import etree
    W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    A='http://schemas.openxmlformats.org/drawingml/2006/main'
    def tag(name):return '{'+W+'}'+name
    temp=Path(path).with_suffix('.normalized.docx')
    with zipfile.ZipFile(path) as source,zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            blob=source.read(item.filename)
            if item.filename.startswith('word/') and item.filename.endswith('.xml'):
                root=etree.fromstring(blob)
                for fonts in root.iter(tag('rFonts')):
                    fonts.attrib.clear()
                    for name,value in {'ascii':'Times New Roman','hAnsi':'Times New Roman','eastAsia':'宋体','cs':'Times New Roman'}.items():fonts.set(tag(name),value)
                for rpr in root.iter(tag('rPr')):
                    for name in ('sz','szCs'):
                        element=rpr.find(tag(name))
                        if element is None:element=etree.SubElement(rpr,tag(name))
                        element.set(tag('val'),'24')
                for spacing in root.iter(tag('spacing')):
                    spacing.set(tag('line'),'240');spacing.set(tag('lineRule'),'auto')
                if root.tag==tag('fonts'):
                    for child in list(root):root.remove(child)
                    for name in ('宋体','Times New Roman'):
                        etree.SubElement(root,tag('font')).set(tag('name'),name)
                for name in ('latin','ea','cs','font'):
                    for element in root.iter('{'+A+'}'+name):
                        if 'typeface' in element.attrib:element.set('typeface','Times New Roman' if name=='latin' else '宋体')
                blob=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
            target.writestr(item,blob)
    # OneDrive/antivirus can briefly hold a freshly written ZIP on Windows.
    import time
    for attempt in range(5):
        try:
            temp.replace(path)
            break
        except PermissionError:
            if attempt==4:raise
            time.sleep(0.25*(2**attempt))

def analyze_template(path):
    doc=Document(convert(Path(path)));sec=doc.sections[0];runs=[r for p in doc.paragraphs for r in p.runs if r.text.strip()]
    from collections import Counter
    sizes=Counter(r.font.size.pt for r in runs if r.font.size)
    fonts=Counter(r.font.name for r in runs if r.font.name)
    return {'page_cm':[round(sec.page_width.cm,2),round(sec.page_height.cm,2)],'margins_cm':[round(getattr(sec,k).cm,2) for k in ('top_margin','bottom_margin','left_margin','right_margin')],'sizes':dict(sizes),'fonts':dict(fonts),'paragraphs':[{'style':p.style.name,'alignment':str(p.alignment),'line_spacing':str(p.paragraph_format.line_spacing),'first_indent':str(p.paragraph_format.first_line_indent),'bold':any(r.bold for r in p.runs)} for p in doc.paragraphs]}
