from openai import OpenAI

client = OpenAI()


def parse_passport(raw_text):

    response = client.chat.completions.create(

        model="gpt-4o",
        temperature=0,

        messages=[
            {
                "role": "system",
                "content": """
Из OCR текста российского паспорта извлеки данные.

Форматы:

Серия — 4 цифры
Номер — 6 цифр
Код подразделения — формат XXX-XXX

Верни строго в формате:

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
"""
            },
            {
                "role": "user",
                "content": raw_text
            }
        ]
    )

    return response.choices[0].message.content