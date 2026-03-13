import os


def build_case_context(case):

    base_folder = f"cases/{case}"

    passport_path = f"{base_folder}/passport/client_data.txt"
    questionnaire_path = f"{base_folder}/materials/questionnaire.txt"
    instances_path = f"{base_folder}/instances.txt"

    context = ""

    # -----------------------------------
    # паспорт
    # -----------------------------------

    if os.path.exists(passport_path):

        with open(passport_path, "r", encoding="utf-8") as f:

            context += "ДАННЫЕ КЛИЕНТА\n"
            context += "--------------------\n"

            context += f.read()
            context += "\n\n"

    # -----------------------------------
    # опросник
    # -----------------------------------

    if os.path.exists(questionnaire_path):

        with open(questionnaire_path, "r", encoding="utf-8") as f:

            context += "ОПРОСНИК\n"
            context += "--------------------\n"

            context += f.read()
            context += "\n\n"

    # -----------------------------------
    # инстанции
    # -----------------------------------

    if os.path.exists(instances_path):

        with open(instances_path, "r", encoding="utf-8") as f:

            context += "ИНСТАНЦИИ\n"
            context += "--------------------\n"

            context += f.read()
            context += "\n\n"

    # -----------------------------------
    # сохраняем
    # -----------------------------------

    context_path = f"{base_folder}/case_context.txt"

    with open(context_path, "w", encoding="utf-8") as f:

        f.write(context)

    return context_path