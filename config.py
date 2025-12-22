import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    DEFAULT_CHAT_ID = os.getenv("DEFAULT_CHAT_ID")  # Опционально
    TIMEZONE = "Europe/Moscow"
    SEND_TIME = "10:00"