import os


def read_instances(case):

    path = f"cases/{case}/materials/instances.txt"

    data = {

        "COURT_NAME": "",
        "COURT_ADDRESS": "",
        "CASE_NUMBER": "",

        "GIBDD_NAME": "",
        "GIBDD_ADDRESS": ""
    }

    if not os.path.exists(path):
        return data

    with open(path, "r", encoding="utf-8") as f:

        for line in f.readlines():

            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            key = key.strip()
            value = value.strip()

            if key in data:

                data[key] = value

    return data
