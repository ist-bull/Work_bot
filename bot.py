import os
import random
import string
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client, Client
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    try:
        supabase.table("telegram_link_codes").insert(
            {
                "code": code,
                "chat_id": chat_id,
                "expires_at": expires_at.isoformat(),
            }
        ).execute()
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
