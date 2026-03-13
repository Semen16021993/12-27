from docx import Document
import subprocess
import os


def generate_document(case, template_name, replacements):

    template_path = f"templates/{template_name}.docx"

    doc = Document(template_path)

    # замена переменных
    for p in doc.paragraphs:

        for run in p.runs:

            for key, value in replacements.items():

                if key in run.text:

                    run.text = run.text.replace(key, value)

    folder = f"cases/{case}/defense"

    os.makedirs(folder, exist_ok=True)

    docx_path = f"{folder}/{template_name}_{case}.docx"

    doc.save(docx_path)

    # конвертация в PDF через LibreOffice

    subprocess.run([
        "/usr/local/bin/soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        folder,
        docx_path
    ], check=True)

    pdf_path = docx_path.replace(".docx", ".pdf")

    return docx_path, pdf_path