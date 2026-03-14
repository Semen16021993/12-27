import os
from services.instances_gpt_parser import parse_instances_with_gpt


def update_instances(case_folder, text):

    path = f"{case_folder}/materials/instances.txt"

    # GPT извлекает структуру
    structured = parse_instances_with_gpt(text)

    # читаем старый файл если есть
    existing = ""

    if os.path.exists(path):

        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()

    # объединяем старые и новые данные
    combined = existing + "\n" + structured

    # сохраняем
    with open(path, "w", encoding="utf-8") as f:

        f.write(combined)

    return "Данные успешно обновлены."