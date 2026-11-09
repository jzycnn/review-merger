import os, json, hashlib, re, datetime, uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(os.environ.get('REVIEW_HOME', str(Path(__file__).resolve().parents[2] / 'data')))
for folder in ('input','sources','converted','exports','backups'):
    (ROOT / folder).mkdir(parents=True, exist_ok=True)
engine = create_engine('sqlite:///' + str(ROOT/'review.db'), connect_args={'check_same_thread':False,'timeout':30})
Base = declarative_base()
class Row(Base):
    __tablename__ = 'records'
    id = Column(String, primary_key=True)
    kind = Column(String, index=True)
    month = Column(String, index=True, default='')
    status = Column(String, default='')
    data = Column(Text)
    version = Column(Integer, default=1)
Base.metadata.create_all(engine)
Session = sessionmaker(engine, expire_on_commit=False)
def uid(): return uuid.uuid4().hex
def put(kind, data, month='', status='', id=None):
    with Session.begin() as s:
        r=Row(id=id or uid(),kind=kind,month=month,status=status,data=json.dumps(data,ensure_ascii=False)); s.add(r)
        return r.id
def rows(kind, month=None):
    with Session() as s:
        q=s.query(Row).filter_by(kind=kind)
        if month is not None: q=q.filter_by(month=month)
        return [pack(r) for r in q.all()]
def pack(r): return dict(id=r.id,kind=r.kind,month=r.month,status=r.status,version=r.version,data=json.loads(r.data))
def get(id):
    with Session() as s:
        r=s.get(Row,id)
        if not r: raise ValueError('记录不存在')
        return pack(r)
def update(id,data,status=None,version=None):
    with Session.begin() as s:
        r=s.get(Row,id)
        if not r: raise ValueError('记录不存在')
        if version is not None and r.version!=version: raise ValueError('内容已被修改，请刷新后重试')
        s.add(Row(id=uid(),kind='history',month=r.month,status=id,data=r.data))
        r.data=json.dumps(data,ensure_ascii=False); r.version+=1
        if status is not None:r.status=status

class Block(BaseModel):
    source_file_id: str
    source_block_id: str
    paragraph_index: int | None = None
    table_index: int | None = None
    original_text: str
    location: str = 'body'
    original_section_title: str = ''
class Section(BaseModel):
    type: Literal['review_opinion','reporter_reflection','editor_comment','unclassified']
    original_heading: str = ''
    heading_id: str | None = None
    source_block_ids: list[str] = Field(default_factory=list)
class Program(BaseModel):
    review_date: str | None = None
    column_name: str = '今日评说'
    program_title: str | None = None
    metadata_ids: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    review_start: str | None = None
    review_end: str | None = None
    reviewers_raw: str = ''
    requires_review: bool = True
class Recognition(BaseModel):
    programs: list[Program]
class Template(BaseModel):
    font: str = '宋体'
    size: float = Field(default=14,ge=8,le=28)
    horizontal_margin_cm: float = Field(default=3.17,ge=1,le=5)
    margin_cm: float = Field(default=2.54,ge=1,le=5)
    line_spacing: float = Field(default=1.5,ge=1,le=3)
    first_indent_pt: float = Field(default=28,ge=0,le=56)
    review_label: Literal['审片意见','修改意见'] = '审片意见'
    show_missing: bool = True
def config():
    r=rows('settings');return r[-1]['data'] if r else {'enabled':False,'base_url':'https://api.openai.com/v1','model':'gpt-4.1-mini'}
