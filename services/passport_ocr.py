import base64
from openai import OpenAI

client = OpenAI()


def ocr_passport(images):

    vision_input = []

    for img_path in images:

        with open(img_path, "rb") as f:
            base64_img = base64.b64encode(f.read()).decode()

        vision_input.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_img}",
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
Ты система OCR.

Твоя задача — переписать ВЕСЬ текст с изображений российского паспорта максимально точно.

Правила:
— переписывай текст дословно
— не извлекай поля
— не интерпретируй
— просто перепиши текст
"""
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Перепиши весь текст"},
                    *vision_input
                ]
            }
        ]
    )

    return response.choices[0].message.content