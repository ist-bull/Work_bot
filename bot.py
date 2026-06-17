import os
import random
import string
from datetime import datetime, timedelta, timezone

import psycopg2
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]  # postgresql://user:pass@host:5432/dbname


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO telegram_link_codes (code, chat_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (code, chat_id, expires_at),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Kod kaydedilemedi: {e}")
        await update.message.reply_text("Bir hata oluştu, lütfen tekrar deneyin.")
        return

    await update.message.reply_text(
        f"Hoş geldiniz! Sistemdeki profil sayfanıza bu kodu girin:\n\n"
        f"🔑 {code}\n\n"
        f"Kod 10 dakika geçerlidir."
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
