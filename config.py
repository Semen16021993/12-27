import os

# TELEGRAM BOT TOKEN
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# OPENAI API KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ОСНОВНЫЕ ПАПКИ ПРОЕКТА
CASES_FOLDER = "cases"
RAG_FOLDER = "rag"

# Разрешенные пользователи Telegram
ALLOWED_USERS = {
    791514191,  # Семен
    915528002,  # Володя
}