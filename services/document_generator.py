from docx import Document
import subprocess
import os


def generate_document(case, template_name, replacements):

    template_path = f"templates/{template_name}"

    doc = Document(template_path)

    # замена переменных
    for p in doc.paragraphs:
        for run in p.runs:
            for key, value in replacements.items():
                if key in run.text:
                    run.text = run.text.replace(key, value)

    folder = f"cases/{case}/defense"
    os.makedirs(folder, exist_ok=True)

    # имя файла без двойных расширений
    base_name = template_name.replace(".docx", "")

    docx_path = f"{folder}/{base_name} {case}.docx"

    doc.save(docx_path)

    subprocess.run([
        "/usr/local/bin/soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        folder,
        docx_path
    ], check=True)

    pdf_path = f"{folder}/{base_name} {case}.pdf"

    return docx_path, pdf_path