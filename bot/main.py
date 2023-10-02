import logging

import requests
from db_handler import WeaviateHandler
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "redacted"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

db_client: WeaviateHandler | None


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [("echo", "Echos stuff"), ("caps", "Caps stuff")]
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=update.message.text
    )


async def caps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_caps = " ".join(context.args).upper()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text_caps)


if __name__ == "__main__":
    print("REEE")
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    echo_handler = CommandHandler("echo", echo)
    caps_handler = CommandHandler("caps", caps)

    application.add_handler(echo_handler)
    application.add_handler(caps_handler)

    db_client = WeaviateHandler()

    application.run_polling()
