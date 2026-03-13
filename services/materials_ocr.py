from openai import OpenAI
from config import OPENAI_API_KEY
import base64

client = OpenAI(api_key=OPENAI_API_KEY)

def ocr_image(path):

    with open(path, "rb") as f:
        image = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Извлеки весь читаемый текст с изображения документа."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "распознай документ"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content