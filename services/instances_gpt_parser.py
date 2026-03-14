from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


PROMPT = """
Ты юридический ассистент.

Твоя задача — из произвольного текста пользователя извлечь данные суда и ГИБДД.

Пользователь может писать как угодно:
— с маленькой буквы
— без знаков препинания
— в одной строке
— в нескольких строках
— в любом порядке

Нужно извлечь:

COURT_NAME
COURT_ADDRESS
CASE_NUMBER
GIBDD_NAME
GIBDD_ADDRESS

Если какого-то поля нет — оставь пустым.

Ответ верни СТРОГО в формате:

COURT_NAME:
COURT_ADDRESS:
CASE_NUMBER:

GIBDD_NAME:
GIBDD_ADDRESS:
"""


def parse_instances_with_gpt(text):

    response = client.chat.completions.create(

        model="gpt-4.1-mini",

        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text}
        ],

        temperature=0
    )

    result = response.choices[0].message.content

    return result