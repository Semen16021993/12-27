from telegram import ReplyKeyboardMarkup


def other_documents_keyboard():

    keyboard = [

        ["Объяснительная"],
        ["Расписка"],

        ["Правовое заключение"],
        ["Отзыв"],

        ["Судебная речь"],
        ["Обжалование"],

        ["Назад"]

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )
