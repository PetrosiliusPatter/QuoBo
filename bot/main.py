import json
import logging
import os
from typing import Callable

from db_handler import DBHandler, Quote
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
from utils import (
    datetime_to_rfc3339,
    get_message_url,
    rfc3339_to_datetime,
    sanitize_markdown,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEAVIATE_API_KEY = os.environ.get("WEAVIATE_API_KEY")

DEBUG = os.environ.get("DEBUG", False)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

db_client: DBHandler | None


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            ("quote", "quote stuff"),
            ("unquote", "unquote stuff"),
            ("embarrass", "embarrass ppl"),
        ]
    )


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    quote_message = update.message.reply_to_message
    command_message_id = update.message.message_id

    if not db_client:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Database is not connected.",
        )
        return

    if not quote_message:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="You need to reply to a message when using /quote.",
        )
        return

    if quote_message.from_user.is_bot:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Bots have nothing interesting to say.",
        )
        return

    quote_poster_uid = quote_message.from_user.id
    if not DEBUG and quote_poster_uid == update.message.from_user.id:
        text = "Quoting yourself? Really?"
        await context.bot.send_message(
            chat_id=chat_id, reply_to_message_id=command_message_id, text=text
        )
        return

    quote_text: str | None

    if quote_message.text and quote_message.text != "":
        quote_text = sanitize_markdown(quote_message)
    else:
        if quote_message.caption and quote_message.caption != "":
            quote_text = sanitize_markdown(quote_message, use_caption=True)
        else:
            context.bot.send_message(
                chat_id=chat_id,
                reply_to_message_id=command_message_id,
                text="There should be something to quote in the message.",
            )
            return

    if not quote_text:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="There should be something to quote in the message.",
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
        post_date=datetime_to_rfc3339(quote_message.date),
        last_quoted=datetime_to_rfc3339(quote_message.date),
    )
    db_client.save_quote(new_quote)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, text="Message saved."
    )


async def embarrass_pseudo_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def quote_picker(account_id: int, _: str):
        return db_client.pseudo_random_quote_for_user(account_id)

    await base_embarrass(update, context, quote_picker)


async def embarrass_semantic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def quote_picker(account_id: int, response_to_text: str):
        query = " ".join(context.args) if len(context.args) > 0 else response_to_text
        return db_client.quote_for_user_by_query(account_id, query)

    await base_embarrass(update, context, quote_picker)


async def base_embarrass(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    quote_picker: Callable[[int, str], Quote],
):
    chat_id = update.effective_chat.id
    response_to_message = update.message.reply_to_message
    command_message_id = update.message.message_id

    if not db_client:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Database is not connected.",
        )
        return

    if not response_to_message:
        await context.bot.send_message(
            chat_id=chat_id,
            text="You need to reply to a message, so I know who to embarrass.",
            reply_to_message_id=command_message_id,
        )
        return

    if response_to_message.from_user.is_bot:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Bots don't embarrass themselves.",
        )
        return

    embarrass_uid = response_to_message.from_user.id
    if not DEBUG and embarrass_uid == update.message.from_user.id:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Why embarrass yourself? Have some self respect.",
        )
        return

    tilt = response_to_message.text or response_to_message.caption
    embarrass_quote = quote_picker(
        embarrass_uid, (response_to_message.text or response_to_message.caption)
    )
    if not embarrass_quote:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Could not find a fitting quote.",
        )
        return

    embarrassed_member = await context.bot.get_chat_member(chat_id, embarrass_uid)
    mention = f'<a href="tg://user?id={embarrass_uid}">{embarrassed_member.user.first_name}</a>'

    chat_title = "Unknown Group"
    try:
        chat = await context.bot.get_chat(embarrass_quote.group_id)
        chat_title = chat.title
    except:
        pass

    message_url = get_message_url(embarrass_quote.group_id, embarrass_quote.message_id)
    parsed_post_date = rfc3339_to_datetime(embarrass_quote.post_date)

    await context.bot.send_message(
        chat_id=chat_id,
        reply_to_message_id=command_message_id,
        text=f'"{embarrass_quote.quote_text}"\n    -{mention}, ({parsed_post_date.year}), {chat_title}, <a href="{message_url}">Telegram</a>',
        parse_mode="HTML",
    )
    return


async def unquote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    quote_message = update.message.reply_to_message
    command_message_id = update.message.message_id

    if not db_client:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Database is not connected.",
        )
        return

    if not quote_message:
        context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="You need to reply to a quoted message when using /unquote.",
        )
        return

    found_quote = db_client.find_quote_by_message_id(quote_message.message_id)
    if found_quote is None:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="This message wasn't quoted.",
        )
        return

    quote_poster_uid = quote_message.from_user.id
    if not DEBUG and quote_poster_uid == update.message.from_user.id:
        await context.bot.send_message(
            chat_id=chat_id,
            reply_to_message_id=command_message_id,
            text="Haha! You wish! This will be remembered forever!",
        )
        return

    db_client.delete_quote_by_id(found_quote.id)
    await context.bot.send_message(
        chat_id=chat_id, reply_to_message_id=command_message_id, text="Message deleted."
    )


if __name__ == "__main__":
    db_client = DBHandler(WEAVIATE_API_KEY)
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    quote_handler = CommandHandler("quote", quote)
    application.add_handler(quote_handler)

    embarrass_handler = CommandHandler("embarrass", embarrass_pseudo_random)
    application.add_handler(embarrass_handler)

    embarrass_semantic_handler = CommandHandler(
        "embarrass_semantic", embarrass_semantic
    )
    application.add_handler(embarrass_semantic_handler)

    unquote_handler = CommandHandler("unquote", unquote)
    application.add_handler(unquote_handler)

    application.run_polling()
