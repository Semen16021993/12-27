import os
from services.materials_ocr import ocr_image
from services.pdf_reader import read_pdf


def process_material(file_path, case_folder):

    text = ""

    if file_path.lower().endswith(".pdf"):

        text = read_pdf(file_path)

    if file_path.lower().endswith((".jpg", ".jpeg", ".png")):

        text = ocr_image(file_path)

    if not text:
        return

    materials_text_path = f"{case_folder}/materials_text.txt"

    with open(materials_text_path, "a", encoding="utf-8") as f:

        f.write("\n\n---------------------------\n")
        f.write(f"Файл: {os.path.basename(file_path)}\n")
        f.write("---------------------------\n\n")
        f.write(text)