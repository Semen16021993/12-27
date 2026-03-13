import base64
import os
from openai import OpenAI

client = OpenAI()


def process_passport(files, case_folder):

    images = []

    for path in files:

        with open(path, "rb") as img:
            base64_image = base64.b64encode(img.read()).decode("utf-8")

        mime = "image/jpeg"

        if path.lower().endswith(".png"):
            mime = "image/png"

        images.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime};base64,{base64_image}",
                "detail": "high"
            }
        })

    response = client.chat.completions.create(

        model="gpt-4o",

        temperature=0,

        messages=[
            {
                "role": "system",
                "content": """
Ты система извлечения данных российского паспорта.

Тебе даются изображения страниц паспорта.

Извлеки данные.

Форматы:

Серия — 4 цифры
Номер — 6 цифр
Код подразделения — формат XXX-XXX

Важно:
Не извлекай дату регистрации по месту жительства.
Нужен только адрес регистрации без даты.

Верни строго:

ФИО:
Пол:
Дата рождения:
Место рождения:
Серия:
Номер:
Кем выдан:
Дата выдачи:
Код подразделения:
Адрес регистрации:

Если поле отсутствует — напиши: Информация отсутствует
"""
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Извлеки данные паспорта"},
                    *images
                ]
            }
        ]
    )

    result = response.choices[0].message.content

    if not result:
        return "Ошибка распознавания паспорта"

    return result