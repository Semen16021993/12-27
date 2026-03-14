from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


PROMPT = """
Ты юридический помощник.

Твоя задача — привести данные клиента и органа в правильный
юридический формат для процессуального документа.

Правила:

1. Названия органов:
   - ГИБДД пишется капсом
   - город с большой буквы
   - улицы с большой буквы
   - добавь точки и запятые при необходимости

2. ФИО:
   Верни три формы:

   CLIENT_NAME_NOM — именительный (Иванов Иван Иванович)
   CLIENT_NAME_GEN — родительный (Иванова Ивана Ивановича)
   CLIENT_SIGNATURE — подпись (Иванов И.И.)

3. Не придумывай данных.
4. Если данных нет — оставь поле пустым.

Ответ верни строго так:

CLIENT_NAME_NOM:
CLIENT_NAME_GEN:
CLIENT_SIGNATURE:

GIBDD_NAME:
GIBDD_ADDRESS:
COURT_NAME:
COURT_ADDRESS:
"""


def format_data(client_fio, gibdd_name, gibdd_address, court_name, court_address):

    prompt = f"""
ФИО клиента:
{client_fio}

ГИБДД:
{gibdd_name}

Адрес ГИБДД:
{gibdd_address}

Суд:
{court_name}

Адрес суда:
{court_address}
"""

    response = client.chat.completions.create(

        model="gpt-4o-mini",

        temperature=0,

        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content