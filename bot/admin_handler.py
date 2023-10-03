import os
from enum import Enum

from db_handler import DBHandler, Quote
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from utils import chunks, progress_bar

ACTION, BACKUP, RECEIVE_DUMP, CONFIRM_RESTORE = range(4)

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

RESTORE_CHUNK_SIZE = 200


class Trigger(Enum):
    BACKUP = "Backup"
    RESTORE = "Restore"
    CONFIRM_RESTORE = "YES!"
    CANCEL_RESTORE = "No"


def get_admin_handler(db_handler: DBHandler):
    backup_unconfirmed: list[Quote] = []

    async def admin_control(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        chat_id = update.effective_chat.id
        if str(chat_id) != ADMIN_CHAT_ID:
            await update.message.reply_text(
                f"This chat ({chat_id}) is not authorized to use the admin panel.\n"
                "Please contact the bot owner to get access."
            )
            return None

        reply_keyboard = [[Trigger.BACKUP.value, Trigger.RESTORE.value]]
        await update.message.reply_text(
            "Welcome to the QuoBo admin panel.\n"
            "Send /cancel to stop talking to me.\n"
            "What would you like to do?\n\n"
            f'(Reply with "{Trigger.BACKUP.value}" or "{Trigger.RESTORE.value}")',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
                one_time_keyboard=True,
                input_field_placeholder="What action would you like to take?",
            ),
        )

        return ACTION

    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "That's all then! Bye!",
            reply_markup=ReplyKeyboardRemove(),
        )

        return ConversationHandler.END

    async def action_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        trigger = update.message.text
        if trigger == Trigger.BACKUP.value:
            await update.message.reply_text("Alright, preparing dump now.")
            quotes = db_handler.get_all_entries()
            dump = "\n".join([quote.to_tsv() for quote in quotes])
            await context.bot.send_document(
                update.message.chat_id,
                dump.encode("utf-8"),
                filename="dump.tsv",
            )
            return ConversationHandler.END

        elif trigger == Trigger.RESTORE.value:
            await update.message.reply_text("Please send me the dump.")
            return RECEIVE_DUMP
        else:
            await update.message.reply_text("Invalid action. Please try again.")
            return ACTION
        return ConversationHandler.END

    async def receive_dump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        backup_unconfirmed.clear()
        try:
            attachement = await update.message.document.get_file()
            dumpfile = await attachement.download_as_bytearray()
            dumpfile_as_str = dumpfile.decode("utf-8")
            for entry in dumpfile_as_str.splitlines():
                values = entry.split("\t")
                if len(values) != 6:
                    continue
                quote = Quote(
                    group_id=values[0],
                    message_id=int(values[1]),
                    quote_text=values[2],
                    account_id=int(values[3]),
                    post_date=values[4],
                    last_quoted=values[5],
                )
                backup_unconfirmed.append(quote)
        except:
            await update.message.reply_text("Invalid dump file. Please try again.")
            return RECEIVE_DUMP

        reply_keyboard = [[Trigger.CONFIRM_RESTORE.value, Trigger.CANCEL_RESTORE.value]]
        await update.message.reply_text(
            f"Found {len(backup_unconfirmed)} quotes. Are you sure you want to restore them?\n"
            "The current database will be overwritten!\n\n"
            f'(Reply with "{Trigger.CONFIRM_RESTORE.value}" or "{Trigger.CANCEL_RESTORE.value}")',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
                one_time_keyboard=True,
                input_field_placeholder="Delete DB and restore from dump?",
            ),
        )
        return CONFIRM_RESTORE

    async def confirm_restore(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if update.message.text != Trigger.CONFIRM_RESTORE.value:
            await update.message.reply_text("Aborting.")
            return ConversationHandler.END

        dump = backup_unconfirmed.copy()

        db_handler.clear_db()
        chunked_backup = chunks(dump, RESTORE_CHUNK_SIZE)

        progress_info_message = await context.bot.send_message(
            update.message.chat_id,
            progress_bar(message="Restoring...", total=len(dump), current=0),
        )

        for ind, chunk in enumerate(chunked_backup):
            db_handler.save_quotes(chunk)
            await progress_info_message.edit_text(
                progress_bar(
                    message="Restoring...",
                    total=len(dump),
                    current=(ind + 1) * RESTORE_CHUNK_SIZE,
                )
            )

        await progress_info_message.edit_text(f"Done!\nRestored {len(dump)} quotes.")

        return ConversationHandler.END

    admin_handler = ConversationHandler(
        entry_points=[CommandHandler("admin_control", admin_control)],
        states={
            ACTION: [
                MessageHandler(
                    filters.Regex(
                        f"^({Trigger.BACKUP.value}|{Trigger.RESTORE.value})$"
                    ),
                    action_chosen,
                )
            ],
            RECEIVE_DUMP: [MessageHandler(filters.ATTACHMENT, receive_dump)],
            CONFIRM_RESTORE: [
                MessageHandler(
                    filters.Regex(
                        f"^({Trigger.CONFIRM_RESTORE.value}|{Trigger.CANCEL_RESTORE.value})$"
                    ),
                    confirm_restore,
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    return admin_handler
