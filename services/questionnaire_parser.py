import openpyxl


def parse_questionnaire(file_path, client_lastname):

    wb = openpyxl.load_workbook(file_path)

    sheet = wb.active

    rows = list(sheet.iter_rows(values_only=True))

    if not rows:
        return None

    headers = rows[0]

    for row in rows[1:]:

        if not row:
            continue

        fio_cell = str(row[1]).lower()

        if client_lastname.lower() in fio_cell:

            result = ""

            for question, answer in zip(headers[1:], row[1:]):

                if question:

                    result += f"Вопрос: {question}\n"
                    result += f"Ответ: {answer}\n\n"

            return result

    return None 