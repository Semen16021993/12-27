import os
from PIL import Image
from pdf2image import convert_from_path


def convert_to_images(path, output_folder):

    images = []

    ext = path.lower().split(".")[-1]

    # если это изображение
    if ext in ["jpg", "jpeg", "png"]:

        img = Image.open(path)

        new_path = os.path.join(output_folder, "page_1.jpg")

        img.convert("RGB").save(new_path)

        images.append(new_path)

    # если это PDF
    elif ext == "pdf":

        pages = convert_from_path(path)

        for i, page in enumerate(pages):

            new_path = os.path.join(output_folder, f"page_{i+1}.jpg")

            page.save(new_path, "JPEG")

            images.append(new_path)

    return images