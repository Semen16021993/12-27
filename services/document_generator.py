from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.text import WD_LINE_SPACING
import subprocess
import os
import re


def set_document_margins(doc):
    """Устанавливает поля документа"""
    sections = doc.sections
    for section in sections:
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)


def style_paragraph(p, is_list=False):
    """Применяет стили к абзацу"""

    if not p.runs:
        p.add_run()

    for run in p.runs:
        run.font.name = "Times New Roman"
        run.font.size = Pt(12)

    fmt = p.paragraph_format

    # стандартные отступы текста
    if not is_list:
        fmt.left_indent = Cm(0.8)
        fmt.first_line_indent = Cm(1.25)

    fmt.right_indent = Cm(0)

    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)

    fmt.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE

    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def replace_placeholders(paragraph, replacements):
    """Заменяет плейсхолдеры в абзаце"""

    for run in paragraph.runs:
        for key, value in replacements.items():

            if key == "{{BODY}}":
                continue

            if key in run.text:
                run.text = run.text.replace(key, value)


def is_numbered_list(text):
    """Определяет нумерованный список"""
    return re.match(r"\d+\.", text)


def is_dash_list(text):
    """Определяет список с тире"""
    return text.startswith(("-", "—", "–", "•"))


def generate_document(case, template_name, replacements):

    template_path = f"templates/{template_name}"
    doc = Document(template_path)

    set_document_margins(doc)

    body_text = replacements.get("{{BODY}}", "")
    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]

    body_index = None

    # ищем {{BODY}}
    for i, p in enumerate(doc.paragraphs):
        replace_placeholders(p, replacements)

        if "{{BODY}}" in p.text:
            body_index = i

    if body_index is None:
        raise Exception("{{BODY}} not found in template")

    body_paragraph = doc.paragraphs[body_index]
    body_paragraph.clear()

    insert_index = body_index

    for i, para in enumerate(paragraphs):

        if i == 0:
            new_p = body_paragraph
        else:
            new_p = doc.paragraphs[insert_index].insert_paragraph_before()

        text = para.strip()

        # ---------- ПРОШУ ----------

        if "ПРОШУ:" in text:

            parts = text.split("ПРОШУ:")

            if parts[0]:
                run = new_p.add_run(parts[0])
                run.font.name = "Times New Roman"
                run.font.size = Pt(12)

            run = new_p.add_run("ПРОШУ:")
            run.bold = True
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

            if len(parts) > 1:
                run = new_p.add_run(parts[1])
                run.font.name = "Times New Roman"
                run.font.size = Pt(12)

            new_p.paragraph_format.space_before = Pt(12)

        else:

            run = new_p.add_run(text)
            run.font.name = "Times New Roman"
            run.font.size = Pt(12)

        # ---------- ОПРЕДЕЛЕНИЕ СПИСКА ----------

        numbered = is_numbered_list(text)
        dashed = is_dash_list(text)

        is_list = numbered or dashed

        # применяем стиль
        style_paragraph(new_p, is_list)

        fmt = new_p.paragraph_format

        # ---------- ФОРМАТ СПИСКОВ ----------

        if numbered:
            fmt.left_indent = Cm(1.5)
            fmt.first_line_indent = Cm(0)

        elif dashed:
            fmt.left_indent = Cm(2)
            fmt.first_line_indent = Cm(0)

        insert_index += 1

    folder = f"cases/{case}/defense"
    os.makedirs(folder, exist_ok=True)

    base_name = template_name.replace(".docx", "")
    docx_path = f"{folder}/{base_name} {case}.docx"

    doc.save(docx_path)

    try:
        subprocess.run([
            "/usr/local/bin/soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            folder,
            docx_path
        ], check=True)

    except Exception as e:
        print(f"Ошибка PDF: {e}")

    pdf_path = f"{folder}/{base_name} {case}.pdf"

    return docx_path, pdf_path