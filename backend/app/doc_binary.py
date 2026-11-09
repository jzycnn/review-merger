"""Conservative Word 97–2003 text reader based on MS-DOC FIB/CLX/PlcPcd.
Formatting is deliberately not inferred. Native results require explicit human review.
"""
import struct
from .core import Block
WARNING='DOC使用内置文本读取，请对照原件核实段落及表格'
def extract_text(path):
    import olefile
    with olefile.OleFileIO(str(path)) as ole:
        if not ole.exists('WordDocument'):raise ValueError('不是受支持的Word二进制DOC文件')
        word=ole.openstream('WordDocument').read()
        def u16(offset):return struct.unpack_from('<H',word,offset)[0]
        def u32(offset):return struct.unpack_from('<I',word,offset)[0]
        if u16(0)!=0xa5ec or u16(2)<0xc1:raise ValueError('仅支持Word97及之后的二进制DOC，请另存DOCX')
        flags=u16(10)
        if flags & (0x100|0x8000):raise ValueError('DOC已加密，请解密后导入')
        table_name='1Table' if flags & 0x200 else '0Table'
        table=ole.openstream(table_name).read()
        pos=32;csw=u16(pos);pos+=2+csw*2
        cslw=u16(pos);lw=pos+2;pos=lw+cslw*4
        if cslw<11:raise ValueError('DOC文件头不完整')
        story_lengths=[u32(lw+i*4) for i in (3,4,5,7,8,9,10)]
        pairs=u16(pos);rg=pos+2
        if pairs<=33:raise ValueError('DOC缺少文本索引')
        fc,lcb=struct.unpack_from('<II',word,rg+33*8)
        clx=table[fc:fc+lcb]
        if len(clx)!=lcb:raise ValueError('DOC文本索引损坏')
        cur=0
        while cur<len(clx) and clx[cur]==1:
            size=struct.unpack_from('<H',clx,cur+1)[0];cur+=3+size
        if cur+5>len(clx) or clx[cur]!=2:raise ValueError('DOC缺少有效文本片段表')
        size=struct.unpack_from('<I',clx,cur+1)[0];plc=clx[cur+5:cur+5+size]
        if len(plc)!=size or size<4 or (size-4)%12:raise ValueError('DOC文本片段表损坏')
        n=(size-4)//12;cps=struct.unpack_from('<'+'I'*(n+1),plc,0)
        if cps[0]!=0 or any(a>b for a,b in zip(cps,cps[1:])):raise ValueError('DOC文本顺序无效')
        chunks=[]
        for i in range(n):
            count=cps[i+1]-cps[i]
            encoded=struct.unpack_from('<I',plc,4*(n+1)+8*i+2)[0]
            compressed=bool(encoded & 0x40000000);offset=encoded & 0x3fffffff
            if compressed:offset//=2
            length=count if compressed else count*2
            raw=word[offset:offset+length]
            if len(raw)!=length:raise ValueError('DOC正文不完整')
            chunks.append(raw.decode('cp1252' if compressed else 'utf-16-le',errors='strict'))
        text=''.join(chunks)
        # CPs count UTF-16 code units, not Python Unicode scalars.
        units=len(text.encode('utf-16-le'))//2
        if units!=cps[-1] or units<sum(story_lengths):raise ValueError('DOC正文长度校验失败')
        if ole.exists('ObjectPool') or '\x01' in text or any(c in text for c in '\x13\x14\x15'):
            raise ValueError('DOC含图片、嵌入对象或域，请用办公软件另存DOCX后核对导入')
        return text

def read_blocks(path,source):
    import re
    text=extract_text(path)
    unknown={c for c in text if ord(c)<32 and c not in '\r\n\t\x07\x0b\x0c\x0e'}
    if unknown:raise ValueError('DOC存在未支持的控制字符，请另存DOCX')
    paragraphs=re.split(r'\r\n|[\r\n\x07\x0b\x0c\x0e]',text)
    return [Block(source_file_id=source,source_block_id=f'{source}:{i}',paragraph_index=i,original_text=t,location='doc_binary').model_dump() for i,t in enumerate(paragraphs) if t.strip()]
