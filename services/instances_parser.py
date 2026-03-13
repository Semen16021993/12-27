import os


def update_instances(case_folder, text):

    path = f"{case_folder}/materials/instances.txt"

    text_lower = text.lower()

    is_gibdd = "гибдд" in text_lower or "огибдд" in text_lower
    is_court = "суд" in text_lower

    existing = ""

    if os.path.exists(path):

        with open(path, "r", encoding="utf-8") as f:
            existing = f.read().lower()

    result = ""

    if is_gibdd:

        if "гибдд:" in existing:

            result += "Данные ГИБДД уже внесены.\n"

        else:

            with open(path, "a", encoding="utf-8") as f:

                f.write("\nГИБДД:\n")
                f.write(text + "\n")

            result += "Данные ГИБДД сохранены.\n"

    if is_court:

        if "суд:" in existing:

            result += "Данные суда уже внесены.\n"

        else:

            with open(path, "a", encoding="utf-8") as f:

                f.write("\nСУД:\n")
                f.write(text + "\n")

            result += "Данные суда сохранены.\n"

    if not is_gibdd and not is_court:

        result = "Не удалось определить ГИБДД или суд."

    return result