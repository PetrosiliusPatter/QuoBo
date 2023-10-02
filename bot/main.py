import json
import logging
import os

from db_handler import Quote, WeaviateHandler
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
from utils import get_message_url, sanitize_markdown, timestamp_as_rfcc

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

db_client: WeaviateHandler | None


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [("echo", "Echos stuff"), ("quote", "quote stuff")]
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=update.message.text
    )


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    quote_message = update.message.reply_to_message
    reply_message = update.message.message_id

    if not quote_message:
        text = "You need to reply to a message when using /quote."
        await context.bot.send_message(
            chat_id=chat_id, reply_to_message_id=reply_message, text=text
        )
        return

    if quote_message.from_user.is_bot:
        text = "Bots have nothing interesting to say."
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=reply_message,
            text=text,
        )
        return

    quote_poster_uid = quote_message.from_user.id
    """ if quote_poster_uid == update.message.from_user.id:
        text = "Quoting yourself? Really?"
        await context.bot.send_message(
            chat_id=chat_id, reply_to_message_id=reply_message, text=text
        )
        return """

    quote_text: str | None

    if quote_message.text and quote_message.text != "":
        quote_text = sanitize_markdown(quote_message)
    else:
        if quote_message.caption and quote_message.caption != "":
            quote_text = sanitize_markdown(quote_message, use_caption=True)
        else:
            text = "There should be something to quote in the message."
            context.bot.send_message(
                chat_id=chat_id, reply_to_message_id=reply_message, text=text
            )
            return

    if not quote_text:
        text = "There should be something to quote in the message."
        await context.bot.send_message(
            chat_id=chat_id, reply_to_message_id=reply_message, text=text
        )
        return

    existing_quote = db_client.find_quote(quote_poster_uid, quote_text)
    if existing_quote is not None:
        if existing_quote.message_id == quote_message.message_id:
            text = "This message is already in the database."
        else:
            text = f'An identical quote by this user already exists <a href="{get_message_url(existing_quote.group_id, existing_quote.message_id)}">here</a>.'
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        return

    new_quote: Quote = Quote(
        group_id=chat_id,
        message_id=quote_message.message_id,
        quote_text=quote_text,
        account_id=quote_poster_uid,
        post_date=timestamp_as_rfcc(quote_message.date),
        last_quoted=timestamp_as_rfcc(quote_message.date),
    )
    db_client.save_quote(new_quote)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Message saved."
    )


if __name__ == "__main__":
    db_client = WeaviateHandler(WEAVIATE_API_KEY)
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    echo_handler = CommandHandler("echo", echo)
    application.add_handler(echo_handler)

    quote_handler = CommandHandler("quote", quote)
    application.add_handler(quote_handler)

    application.run_polling()
