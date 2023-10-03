import re
from datetime import datetime

from telegram import Message


def sanitize_markdown(message: Message, use_caption: bool = False) -> str | None:
    if use_caption:
        if len(message.caption_entities) == 0:
            return message.caption
        message_text = message.caption
        entities = message.caption_entities
    else:
        if len(message.entities) == 0:
            return message.text
        message_text = message.text
        entities = message.entities

    # Replaces @ at the beginning of a word with ＠
    message_text: str = re.sub(r"(\s)@", r"\1＠", message_text)

    # Guarantee that they are in the correct order
    entities = sorted(entities, key=lambda x: x.offset)
    quote = message_text[: entities[0].offset]
    for i in range(len(entities)):
        entity = entities[i]
        start = entity.offset
        end = entity.offset + entity.length
        if i + 1 < len(entities):
            start_next_entity = entities[i + 1].offset
        else:
            start_next_entity = None

        if entity.type == "text_link":
            quote += f'<a href="{entity.url}">{message_text[start:end]}</a>{message_text[end:start_next_entity]}'
            continue
        elif entity.type == "bold":
            tag = "b"
        elif entity.type == "italic":
            tag = "i"
        elif entity.type == "strikethrough":
            tag = "s"
        elif entity.type == "underline":
            tag = "u"
        elif entity.type == "code":
            tag = "code"
        elif entity.type == "pre":
            tag = "pre"
        elif entity.type == "spoiler":
            tag = "tg-spoiler"
        else:
            quote += message_text[start:start_next_entity]
            continue

        quote += f"<{tag}>{message_text[start:end]}</{tag}>{message_text[end:start_next_entity]}"
    return quote


def get_message_url(group_id: int, message_id: int) -> str:
    clean_group_id = str(group_id)[4:]
    return f"https://t.me/c/{clean_group_id}/{message_id}"


def datetime_to_rfc3339(timestamp: datetime) -> str:
    return timestamp.isoformat("T")


def rfc3339_to_datetime(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp)


def chunks(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def progress_bar(message: str, total: int, current: int) -> str:
    filled = int(current / total * 10)
    empty = 10 - filled
    percentage = int(current / total * 100)
    return f"{message}\n[{'█' * filled}{'░' * empty}] {percentage}% ({current}/{total})"
