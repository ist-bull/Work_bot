import logging
import os
import random
import string
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip().strip("\"'")
if TELEGRAM_BOT_TOKEN.startswith("TELEGRAM_BOT_TOKEN="):
    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN.split("=", 1)[1].strip().strip("\"'")
DATABASE_URL = os.environ["DATABASE_URL"]  # postgresql://user:pass@host:5432/dbname
DB_POOL_MIN_CONNECTIONS = int(os.getenv("DB_POOL_MIN_CONNECTIONS", "1"))
DB_POOL_MAX_CONNECTIONS = int(os.getenv("DB_POOL_MAX_CONNECTIONS", "5"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db_pool: ThreadedConnectionPool | None = None
notification_bot = Bot(token=TELEGRAM_BOT_TOKEN)


def init_db_pool() -> None:
    global db_pool

    if db_pool is not None:
        return

    try:
        db_pool = ThreadedConnectionPool(
            DB_POOL_MIN_CONNECTIONS,
            DB_POOL_MAX_CONNECTIONS,
            dsn=DATABASE_URL,
        )
        logger.info("Database connection pool initialized")
    except Exception:
        logger.exception("Database connection pool could not be initialized")
        raise


def close_db_pool() -> None:
    global db_pool

    if db_pool is not None:
        db_pool.closeall()
        db_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_db_connection():
    if db_pool is None:
        init_db_pool()

    conn = None
    try:
        assert db_pool is not None
        conn = db_pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None and db_pool is not None:
            db_pool.putconn(conn)


def generate_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def create_link_code(chat_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM telegram_link_codes
                WHERE expires_at < now()
                   OR (chat_id = %s AND used = false)
                """,
                (chat_id,),
            )

            for _ in range(10):
                code = generate_code()
                cur.execute(
                    """
                    INSERT INTO telegram_link_codes (code, chat_id, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (code) DO NOTHING
                    """,
                    (code, chat_id, expires_at),
                )
                if cur.rowcount == 1:
                    return code

                logger.warning("Generated duplicate Telegram link code, retrying")

            raise RuntimeError("Could not generate a unique Telegram link code")


def is_chat_linked(chat_id: int) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM users
                    WHERE telegram_chat_id = %s
                )
                """,
                (chat_id,),
            )
            return bool(cur.fetchone()[0])


def clear_telegram_chat_id(chat_id: int) -> None:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET telegram_chat_id = NULL
                    WHERE telegram_chat_id = %s
                    """,
                    (chat_id,),
                )
        logger.info("Cleared blocked Telegram chat_id from users table: %s", chat_id)
    except Exception:
        logger.exception("Could not clear Telegram chat_id after Forbidden: %s", chat_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return

    chat_id = update.effective_chat.id

    try:
        code = create_link_code(chat_id)
    except Exception:
        logger.exception("Telegram link code could not be saved for chat_id=%s", chat_id)
        await update.message.reply_text("Bir hata oluştu, lütfen tekrar deneyin.")
        return

    logger.info("Telegram link code created for chat_id=%s", chat_id)
    await update.message.reply_text(
        f"Hoş geldiniz! Sistemdeki profil sayfanıza bu kodu girin:\n\n"
        f"🔑 {code}\n\n"
        f"Kod 10 dakika geçerlidir."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat is None or update.message is None:
        return

    chat_id = update.effective_chat.id

    try:
        linked = is_chat_linked(chat_id)
    except Exception:
        logger.exception("Telegram link status could not be checked for chat_id=%s", chat_id)
        await update.message.reply_text("Bir hata oluştu, lütfen tekrar deneyin.")
        return

    if linked:
        await update.message.reply_text("Hesabınız zaten bağlı.")
    else:
        await update.message.reply_text("Hesabınız henüz bağlı değil.")


async def send_task_notification(
    chat_id: int,
    task_title: str,
    deadline: str,
    notification_type: Literal["new_task", "deadline_reminder"],
) -> bool:
    if notification_type == "new_task":
        title = "🆕 *Yeni görev atandı*"
    elif notification_type == "deadline_reminder":
        title = "⚠️ *Son tarih hatırlatması*"
    else:
        raise ValueError(f"Unsupported notification_type: {notification_type}")

    message = (
        f"{title}\n\n"
        f"*Görev:* {escape_markdown(task_title)}\n"
        f"*Son tarih:* {escape_markdown(deadline)}"
    )

    try:
        await notification_bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(
            "Telegram task notification sent: chat_id=%s type=%s",
            chat_id,
            notification_type,
        )
        return True
    except Forbidden:
        logger.warning("Telegram bot was blocked by chat_id=%s", chat_id)
        clear_telegram_chat_id(chat_id)
        return False
    except TelegramError:
        logger.exception(
            "Telegram task notification could not be sent: chat_id=%s type=%s",
            chat_id,
            notification_type,
        )
        return False


def main() -> None:
    init_db_pool()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["durum", "status"], status))

    logger.info("Bot çalışıyor...")
    try:
        app.run_polling()
    finally:
        close_db_pool()


if __name__ == "__main__":
    main()
