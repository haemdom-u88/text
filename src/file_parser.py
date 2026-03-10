"""
file_parser.py
支持txt/pdf/docx文件的内容提取
"""
import os
from typing import Optional

def parse_txt(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def parse_pdf(file_path: str) -> str:
    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ''
        return text
    except Exception as e:
        return f"[PDF解析失败: {e}]"

def parse_docx(file_path: str) -> str:
    try:
        import docx
        doc = docx.Document(file_path)
        return '\n'.join([p.text for p in doc.paragraphs])
    except Exception as e:
        return f"[Word解析失败: {e}]"

def parse_file(file_path: str) -> Optional[str]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.txt':
        return parse_txt(file_path)
    elif ext == '.pdf':
        return parse_pdf(file_path)
    elif ext in ('.doc', '.docx'):
        return parse_docx(file_path)
    else:
        return None
