#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 股神 使用者手冊.md 轉成 Word (.docx)
- 標題層級 (##, ###) 對應 Word Heading 1/2/3
- 程式碼區塊 ```...``` 用 Courier New + 灰底
- 表格用原生 Word 表格（含表頭粗體）
- 清單（- 開頭）對應 Word bullet list
- 引用（> 開頭）對應 Word Intense Quote
- 自動加上封面 / 頁首頁尾
"""

import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


# ---------- 樣式工具 ----------

def set_cell_shading(cell, color_hex):
    """設定儲存格底色（例：表頭灰底）"""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tc_pr.append(shd)


def set_run_font(run, name="Microsoft JhengHei", size=11, bold=False, color=None):
    """統一字型：中文用微軟正黑、英文用 Calibri（這樣混排最舒服）"""
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), name)   # 中文字型
    rFonts.set(qn('w:ascii'), "Calibri")  # 英文字型
    rFonts.set(qn('w:hAnsi'), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color


def add_page_number_footer(doc):
    """頁尾加頁碼"""
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("第 ")
    set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))
    # PAGE 欄位碼
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'PAGE'
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run_page = p.add_run()
    set_run_font(run_page, size=9, color=RGBColor(0x80, 0x80, 0x80))
    run_page._r.append(fld_begin)
    run_page._r.append(instr)
    run_page._r.append(fld_end)

    run = p.add_run(" 頁 / 共 ")
    set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))
    # NUMPAGES 欄位碼
    fld_begin = OxmlElement('w:fldChar')
    fld_begin.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = 'NUMPAGES'
    fld_end = OxmlElement('w:fldChar')
    fld_end.set(qn('w:fldCharType'), 'end')
    run_total = p.add_run()
    set_run_font(run_total, size=9, color=RGBColor(0x80, 0x80, 0x80))
    run_total._r.append(fld_begin)
    run_total._r.append(instr)
    run_total._r.append(fld_end)

    run = p.add_run(" 頁")
    set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))


def add_header(doc, text="股神 StockTool v0.9.3 使用手冊"):
    section = doc.sections[0]
    header = section.header
    p = header.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(text)
    set_run_font(run, size=9, color=RGBColor(0x80, 0x80, 0x80))


# ---------- Markdown 解析 ----------

class MarkdownParser:
    def __init__(self, doc):
        self.doc = doc
        self.in_code_block = False
        self.code_buffer = []
        self.in_table = False
        self.table_rows = []

    def feed(self, md_text):
        lines = md_text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]

            # 程式碼區塊
            if line.strip().startswith('```'):
                if not self.in_code_block:
                    self.in_code_block = True
                    self.code_buffer = []
                else:
                    self._flush_code()
                    self.in_code_block = False
                i += 1
                continue
            if self.in_code_block:
                self.code_buffer.append(line)
                i += 1
                continue

            # 表格
            if '|' in line and i + 1 < len(lines) and re.match(r'^\s*\|[\s\-:|]+\|\s*$', lines[i + 1]):
                if not self.in_table:
                    self.in_table = True
                    self.table_rows = []
                self.table_rows.append(line)
                i += 1
                continue
            else:
                if self.in_table:
                    self._flush_table()
                    self.in_table = False
                    self.table_rows = []

            # 空行
            if not line.strip():
                i += 1
                continue

            # 分隔線
            if re.match(r'^\s*---\s*$', line):
                # 水平分隔線
                p = self.doc.add_paragraph()
                run = p.add_run('─' * 60)
                set_run_font(run, size=10, color=RGBColor(0xCC, 0xCC, 0xCC))
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                i += 1
                continue

            # 標題
            m = re.match(r'^(#{1,6})\s+(.*)$', line)
            if m:
                level = len(m.group(1))
                text = m.group(2).strip()
                self._add_heading(text, level)
                i += 1
                continue

            # 引用
            if line.startswith('>'):
                text = line[1:].strip()
                p = self.doc.add_paragraph(style='Intense Quote')
                run = p.add_run(text)
                set_run_font(run, size=10.5, color=RGBColor(0x40, 0x40, 0x40))
                i += 1
                continue

            # 清單
            m = re.match(r'^(\s*)[-*]\s+(.*)$', line)
            if m:
                indent = len(m.group(1))
                text = m.group(2)
                # 處理粗體
                p = self.doc.add_paragraph(style='List Bullet')
                if indent >= 2:
                    p.paragraph_format.left_indent = Cm(1.0)
                self._add_inline_runs(p, text)
                i += 1
                continue

            # 一般段落
            p = self.doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            self._add_inline_runs(p, line)

            i += 1

        if self.in_code_block:
            self._flush_code()
        if self.in_table:
            self._flush_table()

    def _add_heading(self, text, level):
        if level == 1:
            p = self.doc.add_heading(text, level=1)
            for run in p.runs:
                set_run_font(run, name="Microsoft JhengHei", size=20, bold=True, color=RGBColor(0x1F, 0x4E, 0x79))
        elif level == 2:
            p = self.doc.add_heading(text, level=2)
            for run in p.runs:
                set_run_font(run, name="Microsoft JhengHei", size=16, bold=True, color=RGBColor(0x2E, 0x74, 0xB5))
            # 標題下方加底色橫條
            pPr = p._element.get_or_add_pPr()
            pBdr = OxmlElement('w:pBdr')
            bottom = OxmlElement('w:bottom')
            bottom.set(qn('w:val'), 'single')
            bottom.set(qn('w:sz'), '8')
            bottom.set(qn('w:color'), '2E74B5')
            pBdr.append(bottom)
            pPr.append(pBdr)
        elif level == 3:
            p = self.doc.add_heading(text, level=3)
            for run in p.runs:
                set_run_font(run, name="Microsoft JhengHei", size=13, bold=True, color=RGBColor(0x40, 0x40, 0x40))
        else:
            p = self.doc.add_heading(text, level=4)
            for run in p.runs:
                set_run_font(run, name="Microsoft JhengHei", size=12, bold=True)

    def _add_inline_runs(self, p, text):
        # 處理 **粗體**、 `code`、 *斜體*
        parts = re.split(r'(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)', text)
        for part in parts:
            if not part:
                continue
            if part.startswith('**') and part.endswith('**'):
                run = p.add_run(part[2:-2])
                set_run_font(run, size=11, bold=True)
            elif part.startswith('`') and part.endswith('`'):
                run = p.add_run(part[1:-1])
                run.font.name = "Consolas"
                rPr = run._element.get_or_add_rPr()
                rFonts = rPr.find(qn('w:rFonts'))
                if rFonts is None:
                    rFonts = OxmlElement('w:rFonts')
                    rPr.append(rFonts)
                rFonts.set(qn('w:ascii'), "Consolas")
                rFonts.set(qn('w:hAnsi'), "Consolas")
                rFonts.set(qn('w:eastAsia'), "Consolas")
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
            elif part.startswith('*') and part.endswith('*'):
                run = p.add_run(part[1:-1])
                set_run_font(run, size=11)
                run.italic = True
            else:
                # 處理超連結 [text](url) 簡化處理
                run = p.add_run(part)
                set_run_font(run, size=11)

    def _flush_code(self):
        if not self.code_buffer:
            return
        text = '\n'.join(self.code_buffer)
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.right_indent = Cm(0.5)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        # 灰底
        pPr = p._element.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), 'F4F4F4')
        pPr.append(shd)
        run = p.add_run(text)
        run.font.name = "Consolas"
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = OxmlElement('w:rFonts')
            rPr.append(rFonts)
        rFonts.set(qn('w:ascii'), "Consolas")
        rFonts.set(qn('w:hAnsi'), "Consolas")
        rFonts.set(qn('w:eastAsia'), "Consolas")
        run.font.size = Pt(9.5)

    def _flush_table(self):
        # 過濾掉對齊行（--- ---）
        rows = [r for r in self.table_rows if not re.match(r'^\s*\|[\s\-:|]+\|\s*$', r)]
        if not rows:
            return
        # 解析
        parsed = []
        for r in rows:
            cells = [c.strip() for c in r.strip().strip('|').split('|')]
            parsed.append(cells)
        n_cols = max(len(row) for row in parsed)
        # 補齊
        for row in parsed:
            while len(row) < n_cols:
                row.append('')
        # 建表
        table = self.doc.add_table(rows=len(parsed), cols=n_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = 'Light Grid Accent 1'
        for i, row in enumerate(parsed):
            for j, cell_text in enumerate(row):
                cell = table.rows[i].cells[j]
                # 清空預設段落
                cell.text = ''
                p = cell.paragraphs[0]
                run = p.add_run(cell_text)
                if i == 0:
                    set_run_font(run, size=10.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))
                    set_cell_shading(cell, '2E74B5')
                else:
                    set_run_font(run, size=10)
        self.doc.add_paragraph()  # 表後空行


# ---------- 主程式 ----------

def add_cover(doc, title, subtitle, version, date):
    """加封面頁"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(120)
    run = p.add_run("📈")
    run.font.size = Pt(72)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(20)
    run = p.add_run(title)
    set_run_font(run, size=36, bold=True, color=RGBColor(0x1F, 0x4E, 0x79))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run(subtitle)
    set_run_font(run, size=18, color=RGBColor(0x40, 0x40, 0x40))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(60)
    run = p.add_run(f"版本：{version}")
    set_run_font(run, size=14, color=RGBColor(0x60, 0x60, 0x60))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    run = p.add_run(f"日期：{date}")
    set_run_font(run, size=14, color=RGBColor(0x60, 0x60, 0x60))

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(120)
    run = p.add_run("William Chang  ·  Taiwan")
    set_run_font(run, size=12, color=RGBColor(0x80, 0x80, 0x80))

    # 換頁
    doc.add_page_break()


def add_toc(doc, md_text):
    """簡易目錄（章節列舉）"""
    doc.add_heading("目錄", level=1)
    headings = re.findall(r'^(#{1,2})\s+(.*)$', md_text, re.MULTILINE)
    for hashes, title in headings:
        level = len(hashes)
        if level == 1:
            continue
        p = doc.add_paragraph()
        if level == 2:
            p.paragraph_format.left_indent = Cm(0)
            run = p.add_run(f"  {title}")
            set_run_font(run, size=11, bold=True)
        else:
            p.paragraph_format.left_indent = Cm(0.8)
            run = p.add_run(f"    · {title}")
            set_run_font(run, size=10.5, color=RGBColor(0x60, 0x60, 0x60))
    doc.add_page_break()


def main():
    here = Path(__file__).parent
    md_path = here / "使用者手冊.md"
    out_path = here / "股神_StockTool_使用者手冊_v0.9.3.docx"

    md_text = md_path.read_text(encoding='utf-8')

    # 拿掉 H1 標題（封面已用）
    md_body = re.sub(r'^#\s+.*$', '', md_text, count=1, flags=re.MULTILINE).lstrip()

    doc = Document()

    # 頁面設定：A4、直向、邊界 2cm
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)

    # 頁首頁尾
    add_header(doc, "股神 StockTool v0.9.3 使用手冊")
    add_page_number_footer(doc)

    # 封面
    add_cover(
        doc,
        title="股神",
        subtitle="StockTool 台股量化選股與回測系統",
        version="v0.9.3-HOTFIX",
        date="2026-06-09",
    )

    # 目錄
    add_toc(doc, md_body)

    # 內文
    parser = MarkdownParser(doc)
    parser.feed(md_body)

    doc.save(str(out_path))
    print(f"✅ Word 文件已產生：{out_path}")
    print(f"   檔案大小：{out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
