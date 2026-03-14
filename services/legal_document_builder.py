import os

from services.instances_reader import read_instances
from services.gpt_document_body import generate_document_body
from services.document_generator import generate_document
from services.document_registry import DOCUMENTS
from services.gpt_data_formatter import format_data


def read_client_data(case):

    path = f"cases/{case}/passport/client_data.txt"

    data = {

        "CLIENT_FIO": "",
        "CLIENT_ADDRESS": "",
        "PHONE": "",
        "EMAIL": ""

    }

    if not os.path.exists(path):

        return data

    with open(path, "r", encoding="utf-8") as f:

        for line in f.readlines():

            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            key = key.strip().lower()
            value = value.strip()

            if key == "фио":

                data["CLIENT_FIO"] = value

            if "адрес" in key:

                data["CLIENT_ADDRESS"] = value

            if key == "телефон":

                data["PHONE"] = value

            if key == "email":

                data["EMAIL"] = value

    return data


def build_document(case, document_type, user_text):

    # получаем шаблон

    template = DOCUMENTS.get(document_type)

    if not template:
        raise Exception(f"Шаблон для документа не найден: {document_type}")

    template_name = template["template"]

    # читаем данные клиента

    client_data = read_client_data(case)

    # читаем данные суда

    instances = read_instances(case) or {}

    # -----------------------------------
    # GPT форматирование данных
    # -----------------------------------

    formatted = format_data(
        client_data["CLIENT_FIO"],
        instances["GIBDD_NAME"],
        instances["GIBDD_ADDRESS"],
        instances["COURT_NAME"],
        instances["COURT_ADDRESS"]
    )

    # парсим ответ GPT
    formatted_data = {}

    for line in formatted.split("\n"):

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        formatted_data[key.strip()] = value.strip()

    # генерируем BODY через GPT

    body = generate_document_body(
        case=case,
        document_type=document_type,
        user_text=user_text
    )

    if not body:
        body = " "

    replacements = {

        "{{CLIENT_FIO}}": formatted_data.get("CLIENT_NAME_NOM", client_data["CLIENT_FIO"]),
        "{{CLIENT_NAME_GEN}}": formatted_data.get("CLIENT_NAME_GEN", ""),
        "{{CLIENT_SIGNATURE}}": formatted_data.get("CLIENT_SIGNATURE", ""),

        "{{CLIENT_ADDRESS}}": client_data.get("CLIENT_ADDRESS", ""),
        "{{PHONE}}": client_data.get("PHONE", ""),
        "{{EMAIL}}": client_data.get("EMAIL", ""),  

        "{{COURT_NAME}}": formatted_data.get("COURT_NAME", instances["COURT_NAME"]),
        "{{COURT_ADDRESS}}": formatted_data.get("COURT_ADDRESS", instances["COURT_ADDRESS"]),
        "{{CASE_NUMBER}}": instances.get("CASE_NUMBER", ""),

        "{{GIBDD_NAME}}": formatted_data.get("GIBDD_NAME", instances["GIBDD_NAME"]),
        "{{GIBDD_ADDRESS}}": formatted_data.get("GIBDD_ADDRESS", instances["GIBDD_ADDRESS"]),

        "{{BODY}}": body

    }

    docx_path, pdf_path = generate_document(

        case,
        template_name,
        replacements

    )

    return docx_path, pdf_path